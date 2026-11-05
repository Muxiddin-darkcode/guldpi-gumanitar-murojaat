import logging
from typing import List, Dict, Any
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import (
    User, Appeal, AppealFile, AppealStatus, AppealType, 
    AppealStatusHistory, AppealTopic, UserRole
)
from database.queries import (
    get_or_create_user, get_active_topics, get_appeal_by_id
)
from keyboards.application import (
    get_appeal_types_keyboard, get_topics_keyboard,
    get_file_upload_keyboard, get_confidentiality_keyboard,
    get_submission_confirm_keyboard
)
from keyboards.main import get_main_menu_keyboard
from states.application import AppealSubmissionState
from states.registration import RegistrationState
from keyboards.user import get_user_type_keyboard
from services.application_service import format_appeal_confirmation
from services.notification_service import notify_new_appeal
from utils.helpers import get_setting, validate_file, log_audit
from utils.number_generator import generate_appeal_number

logger = logging.getLogger(__name__)
router = Router(name="applications_router")


@router.message(F.text.contains("Murojaat yuborish"))
async def start_appeal_submission(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    user = await get_or_create_user(session, message.from_user.id)
    
    # Check registration
    if not user.is_registered:
        await message.answer(
            "⚠️ Murojaat yuborishdan oldin iltimos ro‘yxatdan o‘ting:",
            reply_markup=get_user_type_keyboard()
        )
        await state.set_state(RegistrationState.choosing_user_type)
        return

    # Check if appeals are enabled
    is_enabled = await get_setting(session, "appeals_enabled", "true")
    if is_enabled.lower() != "true":
        await message.answer("⚠️ Hozirda murojaatlar qabul qilish vaqtincha to‘xtatilgan.")
        return

    # Step 1: Appeal Type
    try:
        temp = await message.answer("📝", reply_markup=ReplyKeyboardRemove())
        await temp.delete()
    except Exception:
        pass

    await message.answer(
        "📝 <b>1-bosqich: Murojaat turini tanlang:</b>",
        reply_markup=get_appeal_types_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AppealSubmissionState.choosing_type)


@router.callback_query(F.data == "app_cancel")
async def cancel_submission(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    user = await get_or_create_user(session, callback.from_user.id)
    is_staff = user.role in [
        UserRole.SUPER_ADMIN.value,
        UserRole.DEKAN.value,
        UserRole.ADMINISTRATOR.value,
        UserRole.MASUL_XODIM.value
    ]
    await callback.message.delete()
    await callback.message.answer(
        "❌ Murojaat yuborish bekor qilindi.",
        reply_markup=get_main_menu_keyboard(is_staff=is_staff)
    )
    await callback.answer()


# ------------------- STEP 1: APPEAL TYPE -------------------
@router.callback_query(AppealSubmissionState.choosing_type, F.data.startswith("app_type:"))
async def process_appeal_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    app_type = callback.data.split(":")[1]
    await state.update_data(appeal_type=app_type, files=[])

    # Step 2: Topics
    topics = await get_active_topics(session)
    if not topics:
        await callback.message.edit_text("Hozirda faol yo‘nalishlar topilmadi. Ma'muriyatga murojaat qiling.")
        await state.clear()
        return

    await callback.message.edit_text(
        f"Murojaat turi: <b>{AppealType.label(app_type)}</b>\n\n"
        "🏛 <b>2-bosqich: Fakultetning tegishli yo‘nalishini tanlang:</b>",
        reply_markup=get_topics_keyboard(topics),
        parse_mode="HTML"
    )
    await state.set_state(AppealSubmissionState.choosing_topic)
    await callback.answer()


# ------------------- STEP 2: TOPIC SELECTION -------------------
@router.callback_query(AppealSubmissionState.choosing_topic, F.data.startswith("app_topic:"))
async def process_topic(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    topic_id = int(callback.data.split(":")[1])
    stmt = select(AppealTopic).where(AppealTopic.id == topic_id)
    topic_res = await session.execute(stmt)
    topic = topic_res.scalar_one_or_none()

    if not topic:
        await callback.answer("Yo‘nalish topilmadi!", show_alert=True)
        return

    await state.update_data(topic_id=topic.id, topic_name=topic.name)
    await callback.message.edit_text(
        f"Fakultet yo‘nalishi: <b>{topic.name}</b>\n\n"
        "📌 <b>3-bosqich: Murojaat uchun qisqa sarlavha (mavzu) kiriting:</b>\n"
        "<i>(Masalan: Yakuniy nazorat natijalari bo‘yicha ariza)</i>",
        parse_mode="HTML"
    )
    await state.set_state(AppealSubmissionState.entering_title)
    await callback.answer()


# ------------------- STEP 3: TITLE -------------------
@router.message(AppealSubmissionState.entering_title, F.text)
async def process_title(message: Message, state: FSMContext, session: AsyncSession):
    title = message.text.strip()
    if len(title) < 5 or len(title) > 200:
        await message.answer("Mavzu kamida 5 ta va ko‘pi bilan 200 ta belgidan iborat bo‘lishi kerak. Qaytadan kiriting:")
        return

    min_len = int(await get_setting(session, "min_content_length", "20"))
    max_len = int(await get_setting(session, "max_content_length", "3000"))

    await state.update_data(title=title)
    await message.answer(
        f"Mavzu: <b>{title}</b>\n\n"
        "✍️ <b>4-bosqich: Murojaat mazmunini batafsil yozing:</b>\n"
        f"<i>(Matn uzunligi: {min_len} tadan {max_len} tagacha belgi)</i>",
        parse_mode="HTML"
    )
    await state.set_state(AppealSubmissionState.entering_description)


# ------------------- STEP 4: DESCRIPTION -------------------
@router.message(AppealSubmissionState.entering_description, F.text)
async def process_description(message: Message, state: FSMContext, session: AsyncSession):
    desc = message.text.strip()
    min_len = int(await get_setting(session, "min_content_length", "20"))
    max_len = int(await get_setting(session, "max_content_length", "3000"))

    if len(desc) < min_len:
        await message.answer(f"Murojaat matni juda qisqa! Kamida {min_len} ta belgi bo‘lishi kerak. Iltimos, batafsilroq yozing:")
        return
    if len(desc) > max_len:
        await message.answer(f"Murojaat matni juda uzun! Ko‘pi bilan {max_len} ta belgi bo‘lishi kerak. Qisqartirib yozing:")
        return

    await state.update_data(description=desc)
    await message.answer(
        "📎 <b>5-bosqich: Murojaatga tegishli hujjat yoki fayllarni biriktiring:</b>\n\n"
        "• Ruxsat etilgan fayllar: PDF, DOC, DOCX, JPG, PNG, MP4, XLSX\n"
        "• Bir nechta fayl yuborishingiz mumkin.\n"
        "• Fayllarni yuborib bo‘lgach yoki fayl biriktirishni istamasangiz, quyidagi tugmani bosing.",
        reply_markup=get_file_upload_keyboard(file_count=0),
        parse_mode="HTML"
    )
    await state.set_state(AppealSubmissionState.uploading_files)


# ------------------- STEP 5: FILE UPLOADS -------------------
@router.message(AppealSubmissionState.uploading_files, F.document | F.photo | F.video)
async def process_file_upload(message: Message, state: FSMContext):
    data = await state.get_data()
    files: List[Dict[str, Any]] = data.get("files", [])

    if len(files) >= 5:
        await message.answer("⚠️ Maksimal 5 ta fayl yuklash mumkin. Yakunlash tugmasini bosing.")
        return

    file_id = ""
    file_unique_id = ""
    file_type = "document"
    file_name = None
    file_size = 0

    if message.document:
        doc = message.document
        file_id = doc.file_id
        file_unique_id = doc.file_unique_id
        file_type = "document"
        file_name = doc.file_name
        file_size = doc.file_size
    elif message.photo:
        photo = message.photo[-1]
        file_id = photo.file_id
        file_unique_id = photo.file_unique_id
        file_type = "photo"
        file_name = f"photo_{photo.file_unique_id}.jpg"
        file_size = photo.file_size
    elif message.video:
        video = message.video
        file_id = video.file_id
        file_unique_id = video.file_unique_id
        file_type = "video"
        file_name = video.file_name or f"video_{video.file_unique_id}.mp4"
        file_size = video.file_size

    is_valid, err_msg = validate_file(file_name, file_size)
    if not is_valid:
        await message.answer(f"⚠️ {err_msg}")
        return

    files.append({
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "file_type": file_type,
        "file_name": file_name,
        "file_size": file_size
    })
    await state.update_data(files=files)

    await message.answer(
        f"✅ Fayl qabul qilindi: <b>{file_name or file_type}</b>\n"
        f"Jami biriktirilgan fayllar: {len(files)} ta.",
        reply_markup=get_file_upload_keyboard(file_count=len(files)),
        parse_mode="HTML"
    )


@router.callback_query(AppealSubmissionState.uploading_files, F.data.startswith("file_action:"))
async def process_file_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    # Move to Step 6: Confidentiality
    await callback.message.edit_text(
        "🔒 <b>6-bosqich: Maxfiylik turini tanlang:</b>\n\n"
        "• <b>Oddiy murojaat:</b> Fakultet dekani va barcha vakolatli administratorlar tomonidan ko‘rib chiqiladi.\n"
        "• <b>Maxfiy murojaat:</b> Faqat institut dekani va bosh administratorga yetkaziladi (qolgan xodimlar ko‘ra olmaydi).",
        reply_markup=get_confidentiality_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AppealSubmissionState.choosing_confidentiality)
    await callback.answer()


# ------------------- STEP 6: CONFIDENTIALITY -------------------
@router.callback_query(AppealSubmissionState.choosing_confidentiality, F.data.startswith("confidential:"))
async def process_confidentiality(callback: CallbackQuery, state: FSMContext):
    is_conf = bool(int(callback.data.split(":")[1]))
    await state.update_data(is_confidential=is_conf)

    data = await state.get_data()
    summary_text = format_appeal_confirmation(data)

    await callback.message.edit_text(
        summary_text,
        reply_markup=get_submission_confirm_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AppealSubmissionState.confirming)
    await callback.answer()


# ------------------- STEP 7: FINAL CONFIRMATION -------------------
@router.callback_query(AppealSubmissionState.confirming, F.data == "confirm_submit:edit")
async def edit_appeal_data(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ Murojaatni qaytadan boshlash uchun turini tanlang:",
        reply_markup=get_appeal_types_keyboard()
    )
    await state.set_state(AppealSubmissionState.choosing_type)
    await callback.answer()


@router.callback_query(AppealSubmissionState.confirming, F.data == "confirm_submit:yes")
async def submit_appeal_final(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    if not data:
        await callback.answer("Murojaat allaqachon qabul qilingan yoki bekor bo‘lgan.", show_alert=True)
        return

    tg_user = callback.from_user
    user = await get_or_create_user(session, tg_user.id)

    # Generate atomic appeal number (AF-YYYY-XXXXXX)
    appeal_number = await generate_appeal_number(session)

    # Create Appeal record
    appeal = Appeal(
        appeal_number=appeal_number,
        applicant_id=user.id,
        appeal_type=data.get("appeal_type", "ARIZA"),
        topic_name=data.get("topic_name", "Fakultet faoliyati"),
        title=data.get("title", "Murojaat"),
        description=data.get("description", ""),
        is_confidential=data.get("is_confidential", False),
        status=AppealStatus.YANGI.value
    )
    session.add(appeal)
    await session.flush()  # get appeal.id

    # Add files
    files_data = data.get("files", [])
    for f in files_data:
        app_file = AppealFile(
            appeal_id=appeal.id,
            file_id=f["file_id"],
            file_unique_id=f.get("file_unique_id"),
            file_type=f["file_type"],
            file_name=f.get("file_name"),
            file_size=f.get("file_size")
        )
        session.add(app_file)

    # Initial Status History
    status_entry = AppealStatusHistory(
        appeal_id=appeal.id,
        old_status=None,
        new_status=AppealStatus.YANGI.value,
        changed_by_id=user.id,
        comment="Murojaat tizimda ro‘yxatga olindi"
    )
    session.add(status_entry)

    # Audit log
    await log_audit(
        session=session,
        user_id=user.id,
        telegram_id=user.telegram_id,
        action="CREATE_APPEAL",
        target_type="Appeal",
        target_id=str(appeal.id),
        details=f"Yangi murojaat yaratildi: {appeal_number} ({appeal.appeal_type})"
    )

    await session.commit()
    await state.clear()

    # Exact confirmation text from Section 7:
    success_text = (
        "✅ <b>Murojaatingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"<b>Murojaat raqami:</b> <code>{appeal_number}</code>\n\n"
        "Murojaatingiz Pedagogika fakulteti mas'ullariga yetkazildi.\n\n"
        "Murojaatingiz holatini bot orqali istalgan vaqtda kuzatishingiz mumkin.\n\n"
        "Murojaatingiz uchun rahmat!"
    )

    is_staff = user.role in [
        UserRole.SUPER_ADMIN.value,
        UserRole.DEKAN.value,
        UserRole.ADMINISTRATOR.value,
        UserRole.MASUL_XODIM.value
    ]
    await callback.message.delete()
    await callback.message.answer(
        success_text,
        reply_markup=get_main_menu_keyboard(is_staff=is_staff),
        parse_mode="HTML"
    )
    await callback.answer()

    # Refresh appeal with relationships and notify admins
    refreshed_appeal = await get_appeal_by_id(session, appeal.id)
    if refreshed_appeal:
        await notify_new_appeal(bot=bot, session=session, appeal=refreshed_appeal)

