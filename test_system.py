import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import (
    Base, User, UserType, UserRole, Appeal, AppealFile, 
    AppealStatus, AppealStatusHistory, CorrespondenceMessage, SystemSetting, AppealTopic
)
from database.queries import (
    get_or_create_user, get_appeal_by_id, get_appeal_by_number,
    get_user_appeals_paginated, get_admin_appeals_paginated,
    search_appeals, update_appeal_status, get_dashboard_statistics,
    add_correspondence_message, get_all_staff_members
)
from utils.number_generator import generate_appeal_number
from services.export_service import generate_appeals_excel_report
from services.application_service import format_appeal_detail_view


async def run_tests():
    print("==================================================")
    print("  E-MUROJAAT TIZIMINI TESTLASH VA TEKSHIRISH")
    print("==================================================")

    test_db_path = "data/test_e_murojaat.db"
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

    test_engine = create_async_engine(f"sqlite+aiosqlite:///{test_db_path}")
    TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Test DB Init
    print("\n[1] Baza initsializatsiyasi va standart ma'lumotlar...")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        # Seed settings
        default_settings = {
            "dekan_name": "Komilov Jamoliddin Karimjonovich",
            "institute_name": "Guliston davlat pedagogika instituti",
            "department_name": "Gumanitar fanlar va jismoniy madaniyat fakulteti",
            "contact_phone": "+998 67 225-10-20",
            "contact_email": "komilov.jamoliddin@guldpi.uz",
            "reception_hours": "Har kun: 09:00-17:00",
            "official_telegram": "@gumanitar_fakulteti",
            "default_deadline_days": "10",
            "min_content_length": "20",
            "max_content_length": "3000",
            "appeals_enabled": "true"
        }
        for k, v in default_settings.items():
            session.add(SystemSetting(key=k, value=v))
        
        session.add(AppealTopic(name="Ta'lim jarayoni", is_active=True))
        session.add(AppealTopic(name="Imtihon va baholash", is_active=True))
        await session.commit()

        # Check settings
        res = await session.execute(select(SystemSetting))
        settings_rows = res.scalars().all()
        assert len(settings_rows) >= 5, "Standart sozlamalar bazaga yuklanmadi!"
        print(f" -> OK: {len(settings_rows)} ta tizim sozlamasi mavjud.")

        # 2. Test User Creation
        print("\n[2] Foydalanuvchilarni yaratish va ro'yxatga olish...")
        # Student
        student = await get_or_create_user(session, tg_id=111111, full_name="Aliyev Vali G'ani o'g'li")
        student.user_type = UserType.TALABA.value
        student.direction = "Matematika"
        student.course = 3
        student.group_number = "301-22"
        student.phone = "+998901234567"
        student.is_registered = True

        # Citizen
        citizen = await get_or_create_user(session, tg_id=222222, full_name="Karimov Dilshod O'ktam o'g'li")
        citizen.user_type = UserType.FUQARO.value
        citizen.phone = "+998939876543"
        citizen.region = "Toshkent shahri, Yunusobod tumani"
        citizen.is_registered = True

        # Staff (Dekan)
        dekan = await get_or_create_user(session, tg_id=333333, full_name="Komilov Jamoliddin Karimjonovich")
        dekan.role = UserRole.DEKAN.value
        dekan.user_type = UserType.XODIM.value
        dekan.staff_position = "Gumanitar fanlar va jismoniy madaniyat fakulteti dekani"
        dekan.phone = "+998672251020"
        dekan.is_registered = True

        # Staff (O'qituvchi / Mas'ul xodim)
        teacher = await get_or_create_user(session, tg_id=444444, full_name="Dotsent Sobirov Jasur Karimovich")
        teacher.role = UserRole.MASUL_XODIM.value
        teacher.user_type = UserType.XODIM.value
        teacher.staff_position = "Katta o'qituvchi"
        teacher.phone = "+998904445566"
        teacher.is_registered = True

        await session.commit()
        print(" -> OK: Foydalanuvchilar (Talaba, Fuqaro, Dekan, Mas'ul xodim) muvaffaqiyatli saqlandi.")

        # 3. Test Appeal Number Generation & Submission
        print("\n[3] Murojaat raqamini avtomatik yaratish va saqlash...")
        app_num1 = await generate_appeal_number(session)
        assert app_num1.startswith(f"GF-{datetime.now().year}-"), f"Noto'g'ri format: {app_num1}"
        assert app_num1.endswith("000001"), f"Birinchi raqam 000001 bo'lishi kerak: {app_num1}"

        appeal1 = Appeal(
            appeal_number=app_num1,
            applicant_id=student.id,
            appeal_type="ARIZA",
            topic_name="Imtihon va baholash",
            title="Yakuniy nazorat natijasidan norozilik",
            description="Matematik analiz fanidan yakuniy nazorat ishimni qayta tekshirib berishingizni so'rayman.",
            is_confidential=False,
            status=AppealStatus.YANGI.value
        )
        session.add(appeal1)
        await session.flush()

        # Add attachment
        file1 = AppealFile(
            appeal_id=appeal1.id,
            file_id="tg_doc_123456",
            file_unique_id="uniq_123",
            file_type="document",
            file_name="ariza_nusxasi.pdf",
            file_size=1024 * 350
        )
        session.add(file1)

        # Second appeal (Confidential)
        app_num2 = await generate_appeal_number(session)
        assert app_num2.endswith("000002"), f"Ikkinchi raqam 000002 bo'lishi kerak: {app_num2}"

        appeal2 = Appeal(
            appeal_number=app_num2,
            applicant_id=citizen.id,
            appeal_type="TAKLIF",
            topic_name="Ta'lim jarayoni",
            title="Kafedra laboratoriyasini rivojlantirish bo'yicha taklif",
            description="Kafedraga yangi zamonaviy hisoblash klasterlarini joriy qilish taklifi bilan chiqmoqdaman.",
            is_confidential=True,
            status=AppealStatus.YANGI.value
        )
        session.add(appeal2)

        await session.commit()
        print(f" -> OK: Murojaatlar yaratildi: {app_num1} va {app_num2} (Maxfiy).")

        # 4. Test Status Workflow & Assignment
        print("\n[4] Statuslar o'zgarishi va xodimga biriktirish...")
        # Step: Ko'rib chiqishga olish
        appeal1 = await update_appeal_status(
            session=session,
            appeal_id=appeal1.id,
            new_status=AppealStatus.KORIB_CHIQILMOQDA.value,
            changed_by_id=dekan.id,
            comment="Dekan tomonidan ko'rib chiqishga olindi."
        )
        assert appeal1.status == AppealStatus.KORIB_CHIQILMOQDA.value

        # Step: Mas'ul xodimga biriktirish
        appeal1.assigned_to_id = teacher.id
        appeal1.assigned_by_id = dekan.id
        appeal1.assignment_note = "Imtihon qog'ozini qayta ko'rib chiqib, xulosa berilsin."
        appeal1.deadline = datetime.now(timezone.utc) + timedelta(days=5)
        appeal1.status = AppealStatus.BIRIKTIRILDI.value
        await session.commit()
        print(f" -> OK: Murojaat {appeal1.appeal_number} xodim {teacher.full_name}ga biriktirildi.")

        # 5. Correspondence & Internal Notes
        print("\n[5] Dekanat bilan yozishmalar va ichki izohlar...")
        # Internal note (Only staff sees)
        internal_note = await add_correspondence_message(
            session=session,
            appeal_id=appeal1.id,
            sender_id=teacher.id,
            message_text="Talabaning ishi tekshirildi, 2-savolda hisoblash xatosi bor ekan.",
            is_internal=True
        )
        assert internal_note.is_internal is True

        # Official message from user
        user_msg = await add_correspondence_message(
            session=session,
            appeal_id=appeal1.id,
            sender_id=student.id,
            message_text="Qo'shimcha ma'lumot: Men 12-bilet savollariga javob bergan edim.",
            is_internal=False
        )
        assert user_msg.is_internal is False
        print(" -> OK: Xabarlar saqlandi (ichki izoh va rasmiy yozishma ajratilgan).")

        # 6. Official Resolution
        print("\n[6] Rasmiy javob yuborish va murojaatni yakunlash...")
        appeal1.response_text = "Hurmatli talaba, ishingiz qayta tekshirildi va qo'shimcha 5 ball qo'shildi."
        appeal1.status = AppealStatus.HAL_QILINDI.value
        appeal1.responded_by_id = dekan.id
        appeal1.responded_at = datetime.now(timezone.utc)
        appeal1.completed_at = datetime.now(timezone.utc)
        await session.commit()
        print(" -> OK: Murojaat ijobiy hal etildi va rasmiy javob biriktirildi.")

        # 7. Test Paginated & Filtered Queries
        print("\n[7] Sahifalash va xavfsizlik tekshiruvlari...")
        # Student only sees their appeals
        stud_apps, stud_total = await get_user_appeals_paginated(session, user_id=student.id)
        assert stud_total == 1, f"Talaba faqat o'zining 1 ta murojaatini ko'rishi kerak, lekin {stud_total}"

        # Staff queries (confidential check)
        # Without confidential permission
        staff_apps_public, total_pub = await get_admin_appeals_paginated(session, allow_confidential=False)
        assert total_pub == 1, f"Oddiy xodim maxfiy murojaatni ko'rmasligi kerak, lekin {total_pub}"

        # With confidential permission (Dekan / Super Admin)
        dekan_apps, total_dekan = await get_admin_appeals_paginated(session, allow_confidential=True)
        assert total_dekan == 2, f"Dekan 2 ta murojaatni ham ko'rishi kerak, lekin {total_dekan}"
        print(" -> OK: RBAC va maxfiylik filtrlari to'g'ri ishladi.")

        # 8. Test Search
        print("\n[8] Qidiruv tizimini tekshirish...")
        srch_res = await search_appeals(session, query="Yakuniy nazorat")
        assert len(srch_res) >= 1
        print(f" -> OK: Qidiruv orqali {len(srch_res)} ta murojaat topildi.")

        # 9. Test Statistics
        print("\n[9] Statistika hisob-kitoblarini tekshirish...")
        stats = await get_dashboard_statistics(session)
        assert stats["total"] == 2
        assert stats["hal_qilindi"] == 1
        assert stats["talabalar"] == 1
        assert stats["fuqarolar"] == 1
        print(f" -> OK: Statistika hisoblandi: Jami: {stats['total']}, Hal etildi: {stats['hal_qilindi']}")

        # 10. Test Excel Export (.xlsx)
        print("\n[10] Excel hisobotini (.xlsx) openpyxl bilan generatsiya qilish...")
        excel_path = await generate_appeals_excel_report(session)
        assert os.path.exists(excel_path), f"Excel fayli yaratilmadi: {excel_path}"
        file_size = os.path.getsize(excel_path)
        assert file_size > 1000, f"Excel fayl hajmi juda kichik: {file_size} bayt"
        print(f" -> OK: Excel hisoboti shakllantirildi: {excel_path} ({file_size} bayt).")

    # 11. Test UptimeRobot Keep-Alive Web Server
    print("\n[11] UptimeRobot Keep-Alive veb-serverini tekshirish...")
    from aiohttp.test_utils import TestClient, TestServer
    from services.web_server import create_web_app

    web_app = create_web_app()
    test_client = TestClient(TestServer(web_app))
    await test_client.start_server()

    resp = await test_client.get('/')
    assert resp.status == 200, f"GET / status: {resp.status}"
    resp_health = await test_client.get('/health')
    assert resp_health.status == 200, f"GET /health status: {resp_health.status}"
    health_json = await resp_health.json()
    assert health_json.get("status") == "healthy"
    await test_client.close()
    print(" -> OK: UptimeRobot veb-serveri 200 OK qaytarmoqda (GET / va GET /health).")

    await test_engine.dispose()
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

    print("\n==================================================")
    print("  BARCHA TESTLAR MUVAFFAQIYATLI O'TDI! (100% OK)")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
