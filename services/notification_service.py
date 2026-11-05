import logging
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Appeal, User, AppealStatus, UserRole
from database.queries import get_admins_for_notification, get_user_by_id
from keyboards.admin import get_appeal_card_actions
from utils.helpers import format_datetime

logger = logging.getLogger(__name__)


async def notify_new_appeal(bot: Bot, session: AsyncSession, appeal: Appeal) -> None:
    """
    Sends new appeal notification to Dekan and authorized administrators (Section 9).
    """
    admins = await get_admins_for_notification(session, is_confidential=appeal.is_confidential)
    
    applicant = appeal.applicant
    files_count = len(appeal.files) if appeal.files else 0
    files_text = f"{files_count} ta biriktirilgan fayl" if files_count > 0 else "Fayl yo'q"
    confidential_text = "🔒 Maxfiy (Faqat Dekan)" if appeal.is_confidential else "🌐 Oddiy"

    text = (
        f"📩 <b>YANGI MUROJAAT</b>\n\n"
        f"<b>Murojaat raqami:</b> <code>{appeal.appeal_number}</code>\n"
        f"<b>Murojaatchi:</b> {applicant.full_name}\n"
        f"<b>Turi:</b> {applicant.user_type}\n"
        f"<b>Telefon:</b> {applicant.phone}\n"
        f"<b>Yo‘nalishi:</b> {appeal.topic_name}\n"
        f"<b>Murojaat turi:</b> {appeal.appeal_type}\n"
        f"<b>Mavzu:</b> {appeal.title}\n"
        f"<b>Mazmuni:</b>\n{appeal.description}\n\n"
        f"<b>Sana:</b> {format_datetime(appeal.created_at)}\n"
        f"<b>Maxfiylik:</b> {confidential_text}\n"
        f"<b>Biriktirilgan fayllar:</b> {files_text}\n"
    )

    for admin in admins:
        try:
            # Inline keyboard actions
            kb = get_appeal_card_actions(appeal, current_user_role=admin.role, back_filter="YANGI")
            await bot.send_message(
                chat_id=admin.telegram_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning(f"Could not notify admin {admin.telegram_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error notifying admin {admin.telegram_id}: {e}")


async def notify_status_change(
    bot: Bot,
    session: AsyncSession,
    appeal: Appeal,
    new_status: str,
    comment: Optional[str] = None
) -> None:
    """
    Notifies applicant when their appeal status changes (Section 12).
    """
    applicant = appeal.applicant
    if not applicant or not applicant.telegram_id:
        return

    status_label = AppealStatus.label(new_status)
    text = (
        f"📢 <b>MUROJAAT HOLATI O‘ZGARDI</b>\n\n"
        f"<b>Murojaat raqami:</b> <code>{appeal.appeal_number}</code>\n"
        f"<b>Mavzu:</b> {appeal.title}\n"
        f"<b>Yangi holat:</b> {status_label}\n"
        f"<b>Sana:</b> {format_datetime(appeal.updated_at)}\n"
    )
    if comment:
        text += f"\n<b>Qo‘shimcha izoh / sabab:</b>\n{comment}\n"

    text += "\nMurojaatingiz holatini bot orqali doimiy kuzatib borishingiz mumkin."

    try:
        await bot.send_message(
            chat_id=applicant.telegram_id,
            text=text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {applicant.telegram_id} about status change: {e}")


async def notify_staff_assignment(
    bot: Bot,
    session: AsyncSession,
    appeal: Appeal,
    staff: User,
    assigner: Optional[User] = None
) -> None:
    """
    Notifies responsible staff when an appeal is assigned to them (Section 11).
    """
    if not staff.telegram_id:
        return

    assigner_name = assigner.full_name if assigner else "Dekanat"
    deadline_str = format_datetime(appeal.deadline) if appeal.deadline else "Belgilanmagan"
    instruction = appeal.assignment_note or "Murojaatni o'rganib chiqib, javob loyihasini tayyorlash."

    text = (
        f"📋 <b>SIZGA YANGI MUROJAAT BIRIKTIRILDI!</b>\n\n"
        f"<b>Murojaat raqami:</b> <code>{appeal.appeal_number}</code>\n"
        f"<b>Biriktirdi:</b> {assigner_name}\n"
        f"<b>Murojaatchi:</b> {appeal.applicant.full_name} ({appeal.applicant.phone})\n"
        f"<b>Mavzu:</b> {appeal.title}\n"
        f"<b>Yo‘nalishi:</b> {appeal.topic_name}\n"
        f"<b>Ijro muddati:</b> ⏳ {deadline_str}\n\n"
        f"<b>Topshiriq mazmuni:</b>\n{instruction}\n\n"
        f"Iltimos, belgilangan muddatda murojaatni ko‘rib chiqib, o‘z xulosangizni taqdim eting."
    )

    kb = get_appeal_card_actions(appeal, current_user_role=staff.role, back_filter="ALL")

    try:
        await bot.send_message(
            chat_id=staff.telegram_id,
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify staff {staff.telegram_id}: {e}")


async def notify_official_response(
    bot: Bot,
    appeal: Appeal,
    response_text: str
) -> None:
    """
    Sends official response directly to applicant.
    """
    applicant = appeal.applicant
    if not applicant or not applicant.telegram_id:
        return

    text = (
        f"🏛 <b>GUMANITAR FANLAR VA JISMONIY MADANIYAT FAKULTETIDAN RASMIY JAVOB</b>\n\n"
        f"<b>Murojaat raqami:</b> <code>{appeal.appeal_number}</code>\n"
        f"<b>Mavzu:</b> {appeal.title}\n\n"
        f"<b>Rasmiy javob matni:</b>\n"
        f"{response_text}\n\n"
        f"<b>Javob berilgan sana:</b> {format_datetime(appeal.responded_at)}\n"
        f"<b>Holat:</b> {AppealStatus.label(appeal.status)}\n\n"
        f"Agar savollaringiz bo‘lsa, ushbu murojaat yuzasidan dekanat bilan muloqot qilishingiz mumkin."
    )

    try:
        await bot.send_message(
            chat_id=applicant.telegram_id,
            text=text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not send official response to {applicant.telegram_id}: {e}")

