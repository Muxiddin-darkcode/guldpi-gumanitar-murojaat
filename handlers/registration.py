import logging
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User, UserType, UserRole
from database.queries import get_or_create_user
from keyboards.main import get_main_menu_keyboard, get_cancel_keyboard
from keyboards.user import (
    get_user_type_keyboard, get_phone_request_keyboard,
    get_course_keyboard, get_relationship_keyboard, get_consent_keyboard
)
from states.registration import RegistrationState
from utils.helpers import normalize_phone, log_audit

logger = logging.getLogger(__name__)
router = Router(name="registration_router")


PRIVACY_TEXT = (
    "🔒 <b>SHAXSIY MA'LUMOTLAR MAXFIYLIGI VA ROZILIK</b>\n\n"
    "Kiritilgan shaxsiy ma'lumotlaringiz O‘zbekiston Respublikasining <i>«Jismoniy va yuridik shaxslarning "
    "murojaatlari to‘g‘risida»</i>gi hamda <i>«Shaxsga doir ma'lumotlar to‘g‘risida»</i>gi Qonunlariga muvofiq "
    "faqatgina murojaatingizni ro‘yxatga olish, ko‘rib chiqish va rasmiy javob qaytarish maqsadida xavfsiz "
    "saqlanadi va qayta ishlanadi.\n\n"
    "Shaxsiy ma'lumotlaringiz qayta ishlanishiga roziligingizni tasdiqlaysizmi?"
)


@router.callback_query(F.data.startswith("register_type:"))
async def on_user_type_selected(callback: CallbackQuery, state: FSMContext):
    user_type = callback.data.split(":")[1]
    await state.update_data(user_type=user_type)

    if user_type == UserType.TALABA.value:
        await callback.message.edit_text(
            "🎓 <b>Talaba sifatida ro‘yxatdan o‘tish</b>\n\nFamiliyangizni kiriting:",
            parse_mode="HTML"
        )
        await state.set_state(RegistrationState.waiting_last_name)

    elif user_type == UserType.FUQARO.value:
        await callback.message.edit_text(
            "👤 <b>Fuqaro sifatida ro‘yxatdan o‘tish</b>\n\nFamiliyangizni kiriting:",
            parse_mode="HTML"
        )
        await state.set_state(RegistrationState.waiting_last_name)

    elif user_type == UserType.OTA_ONA.value:
        await callback.message.edit_text(
            "👨‍👩‍👧 <b>Ota-ona sifatida ro‘yxatdan o‘tish</b>\n\nTo‘liq F.I.Sh.ingizni kiriting (Masalan: Eshmatov Toshmat Ali o‘g‘li):",
            parse_mode="HTML"
        )
        await state.set_state(RegistrationState.waiting_full_name)

    elif user_type == UserType.XODIM.value:
        await callback.message.edit_text(
            "🏢 <b>Institut xodimi sifatida ro‘yxatdan o‘tish</b>\n\nTo‘liq F.I.Sh.ingizni kiriting:",
            parse_mode="HTML"
        )
        await state.set_state(RegistrationState.waiting_full_name)

    else:  # BOSHQA
        await callback.message.edit_text(
            "👥 <b>Ro‘yxatdan o‘tish</b>\n\nTo‘liq F.I.Sh.ingizni kiriting:",
            parse_mode="HTML"
        )
        await state.set_state(RegistrationState.waiting_full_name)

    await callback.answer()


# ------------------- TALABA & FUQARO: LAST NAME -------------------
@router.message(RegistrationState.waiting_last_name)
async def process_last_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("Familiya 2 tadan 50 tagacha belgidan iborat bo‘lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(last_name=name)
    await message.answer("Ismingizni kiriting:")
    await state.set_state(RegistrationState.waiting_first_name)


@router.message(RegistrationState.waiting_first_name)
async def process_first_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("Ism 2 tadan 50 tagacha belgidan iborat bo‘lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(first_name=name)
    await message.answer("Otasining ismini (sharifingizni) kiriting (agar mavjud bo‘lsa):")
    await state.set_state(RegistrationState.waiting_middle_name)


@router.message(RegistrationState.waiting_middle_name)
async def process_middle_name(message: Message, state: FSMContext):
    data = await state.get_data()
    user_type = data.get("user_type")
    middle_name = message.text.strip()
    full_name = f"{data.get('last_name')} {data.get('first_name')} {middle_name}".strip()
    await state.update_data(middle_name=middle_name, full_name=full_name)

    if user_type == UserType.TALABA.value:
        await message.answer("Ta'lim yo‘nalishingizni kiriting (Masalan: Matematika, Amaliy matematika, Fizika):")
        await state.set_state(RegistrationState.waiting_direction)
    else:  # FUQARO
        await message.answer("Yashash hududingiz (viloyat/shahar/tuman):")
        await state.set_state(RegistrationState.waiting_region)


# ------------------- TALABA SPECIFIC -------------------
@router.message(RegistrationState.waiting_direction)
async def process_direction(message: Message, state: FSMContext):
    direction = message.text.strip()
    await state.update_data(direction=direction)
    await message.answer("Tahsil olayotgan kursingizni tanlang:", reply_markup=get_course_keyboard())
    await state.set_state(RegistrationState.waiting_course)


@router.callback_query(RegistrationState.waiting_course, F.data.startswith("course:"))
async def process_course(callback: CallbackQuery, state: FSMContext):
    course_num = int(callback.data.split(":")[1])
    await state.update_data(course=course_num)
    await callback.message.edit_text(f"Kurs: {course_num}\n\nAkademik guruh raqamingizni kiriting (Masalan: 210-22):")
    await state.set_state(RegistrationState.waiting_group)
    await callback.answer()


@router.message(RegistrationState.waiting_group)
async def process_group(message: Message, state: FSMContext):
    group = message.text.strip()
    await state.update_data(group_number=group)
    await message.answer(
        "📱 Telefon raqamingizni yuboring yoki quyidagi formatda kiriting: <b>+998901234567</b>",
        reply_markup=get_phone_request_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationState.waiting_phone)


# ------------------- FUQARO SPECIFIC -------------------
@router.message(RegistrationState.waiting_region)
async def process_region(message: Message, state: FSMContext):
    region = message.text.strip()
    await state.update_data(region=region)
    await message.answer(
        "📱 Telefon raqamingizni yuboring yoki quyidagi formatda kiriting: <b>+998901234567</b>",
        reply_markup=get_phone_request_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationState.waiting_phone)


# ------------------- OTA-ONA / XODIM / BOSHQA FULL NAME -------------------
@router.message(RegistrationState.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 4:
        await message.answer("F.I.Sh. to‘liq kiritilishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(full_name=name)
    data = await state.get_data()
    user_type = data.get("user_type")

    if user_type == UserType.OTA_ONA.value:
        await message.answer("Talabaga qarindoshlik munosabatingizni tanlang:", reply_markup=get_relationship_keyboard())
        await state.set_state(RegistrationState.waiting_relationship)
    elif user_type == UserType.XODIM.value:
        await message.answer("Kafedra yoki bo‘limingiz hamda lavozimingizni kiriting:")
        await state.set_state(RegistrationState.waiting_organization)
    else:  # BOSHQA
        await message.answer("Tashkilotingiz yoki faoliyat turingiz (ixtiyoriy, o‘tkazib yuborish uchun '-' yuboring):")
        await state.set_state(RegistrationState.waiting_organization)


@router.callback_query(RegistrationState.waiting_relationship, F.data.startswith("rel:"))
async def process_relationship(callback: CallbackQuery, state: FSMContext):
    rel = callback.data.split(":")[1]
    await state.update_data(relationship=rel)
    await callback.message.edit_text(f"Qarindoshlik: {rel}\n\nFarzandingiz tahsil olayotgan guruh raqami (agar bilsangiz, aks holda '-' yuboring):")
    await state.set_state(RegistrationState.waiting_child_group)
    await callback.answer()


@router.message(RegistrationState.waiting_child_group)
async def process_child_group(message: Message, state: FSMContext):
    grp = message.text.strip()
    await state.update_data(child_group=grp if grp != "-" else "")
    await message.answer(
        "📱 Telefon raqamingizni yuboring yoki quyidagi formatda kiriting: <b>+998901234567</b>",
        reply_markup=get_phone_request_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationState.waiting_phone)


@router.message(RegistrationState.waiting_organization)
async def process_organization(message: Message, state: FSMContext):
    org = message.text.strip()
    await state.update_data(organization=org if org != "-" else "")
    await message.answer(
        "📱 Telefon raqamingizni yuboring yoki quyidagi formatda kiriting: <b>+998901234567</b>",
        reply_markup=get_phone_request_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationState.waiting_phone)


# ------------------- PHONE HANDLER (CONTACT OR TEXT) -------------------
@router.message(RegistrationState.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    normalized = normalize_phone(phone)
    if not normalized:
        await message.answer("Telefon raqami noto‘g‘ri formatda. Iltimos, qaytadan yuboring:")
        return
    await state.update_data(phone=normalized)
    # Remove reply keyboard and show privacy consent
    await message.answer("Rahmat!", reply_markup=ReplyKeyboardRemove())
    await message.answer(PRIVACY_TEXT, reply_markup=get_consent_keyboard(), parse_mode="HTML")
    await state.set_state(RegistrationState.waiting_consent)


@router.message(RegistrationState.waiting_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    normalized = normalize_phone(phone)
    if not normalized:
        await message.answer(
            "⚠️ Telefon raqam formati noto‘g‘ri!\nIltimos, telefon raqamingizni quyidagi formatda kiriting: <b>+998901234567</b> yoki tugmani bosing.",
            parse_mode="HTML"
        )
        return
    await state.update_data(phone=normalized)
    await message.answer("Rahmat!", reply_markup=ReplyKeyboardRemove())
    await message.answer(PRIVACY_TEXT, reply_markup=get_consent_keyboard(), parse_mode="HTML")
    await state.set_state(RegistrationState.waiting_consent)


# ------------------- CONSENT STEP -------------------
@router.callback_query(RegistrationState.waiting_consent, F.data == "consent:agree")
async def process_consent_agree(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    tg_user = callback.from_user

    user = await get_or_create_user(session, tg_user.id)
    user.user_type = data.get("user_type", UserType.TALABA.value)
    user.full_name = data.get("full_name", tg_user.full_name or "Foydalanuvchi")
    user.first_name = data.get("first_name")
    user.last_name = data.get("last_name")
    user.middle_name = data.get("middle_name")
    user.phone = data.get("phone", "")
    user.direction = data.get("direction")
    user.course = data.get("course")
    user.group_number = data.get("group_number")
    user.region = data.get("region")
    user.parent_relation = data.get("relationship")
    user.child_group = data.get("child_group")
    user.organization = data.get("organization")
    user.is_registered = True

    await log_audit(
        session=session,
        user_id=user.id,
        telegram_id=user.telegram_id,
        action="REGISTER_USER",
        target_type="User",
        target_id=str(user.id),
        details=f"Foydalanuvchi ro'yxatdan o'tdi: {user.full_name} ({user.user_type})"
    )

    await session.commit()
    await state.clear()

    is_staff = user.role in [
        UserRole.SUPER_ADMIN.value,
        UserRole.DEKAN.value,
        UserRole.ADMINISTRATOR.value,
        UserRole.MASUL_XODIM.value
    ]

    await callback.message.delete()
    await callback.message.answer(
        f"✅ <b>Ro‘yxatdan o‘tish muvaffaqiyatli yakunlandi!</b>\n\n"
        f"Hurmatli <b>{user.full_name}</b>, endi Siz Pedagogika fakultetiga ariza, taklif va savollaringizni to‘g‘ridan-to‘g‘ri yuborishingiz mumkin.",
        reply_markup=get_main_menu_keyboard(is_staff=is_staff),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(RegistrationState.waiting_consent, F.data == "consent:decline")
async def process_consent_decline(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Ro‘yxatdan o‘tish bekor qilindi. Qonunchilikka ko‘ra, shaxsiy ma'lumotlar qayta ishlanishiga rozilik bildirilmasa, murojaatlar qabul qilinmaydi.\n\nQayta boshlash uchun /start buyrug‘ini yuboring."
    )
    await callback.answer()
