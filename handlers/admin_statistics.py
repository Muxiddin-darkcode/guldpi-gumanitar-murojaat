import logging
from datetime import datetime, timezone, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User
from database.queries import get_or_create_user, get_dashboard_statistics
from keyboards.admin import get_statistics_menu
from services.export_service import generate_appeals_excel_report
from states.admin import AdminBroadcastState
from utils.helpers import get_current_time

logger = logging.getLogger(__name__)
router = Router(name="admin_statistics_router")


def format_stats_text(stats: dict, period_name: str) -> str:
    return (
        f"📊 <b>GUMANITAR FANLAR VA JISMONIY MADANIYAT FAKULTETI | STATISTIKA VA HISOBOTLAR</b>\n"
        f"<i>Davr: {period_name}</i>\n\n"
        f"<b>Murojaatlar ko‘rsatkichlari:</b>\n"
        f"• 📋 Jami murojaatlar: <b>{stats['total']} ta</b>\n"
        f"• 📥 Yangi tushganlar: <b>{stats['yangi']} ta</b>\n"
        f"• 🔄 Ko‘rib chiqilmoqda / Ijroda: <b>{stats['korib_chiqilmoqda']} ta</b>\n"
        f"• ✅ Ijobiy hal etilganlar: <b>{stats['hal_qilindi']} ta</b>\n"
        f"• ❌ Rad etilganlar: <b>{stats['rad_etildi']} ta</b>\n"
        f"• ⏳ Muddati o‘tganlar: <b>{stats['overdue']} ta</b>\n\n"
        f"<b>Murojaatchilar toifalari bo‘yicha:</b>\n"
        f"• 🎓 Talabalar: <b>{stats['talabalar']} ta</b>\n"
        f"• 👤 Fuqarolar: <b>{stats['fuqarolar']} ta</b>\n\n"
        f"<b>Murojaat turlari bo‘yicha:</b>\n"
        f"• 📄 Arizalar: <b>{stats['arizalar']} ta</b>\n"
        f"• ⚠️ Shikoyatlar: <b>{stats['shikoyatlar']} ta</b>\n"
        f"• 💡 Takliflar: <b>{stats['takliflar']} ta</b>\n\n"
        f"<i>Hisobot vaqti: {get_current_time().strftime('%d.%m.%Y %H:%M')}</i>"
    )


@router.callback_query(F.data == "admin_nav:statistics")
async def show_statistics_main(callback: CallbackQuery, session: AsyncSession):
    stats = await get_dashboard_statistics(session)
    text = format_stats_text(stats, "Barcha davr")
    await callback.message.edit_text(text, reply_markup=get_statistics_menu(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("stats_period:"))
async def filter_statistics_period(callback: CallbackQuery, session: AsyncSession):
    period = callback.data.split(":")[1]
    now = datetime.now(timezone.utc)

    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_name = "Bugungi kun"
    elif period == "week":
        start_date = now - timedelta(days=7)
        period_name = "So‘nggi 7 kun"
    elif period == "month":
        start_date = now - timedelta(days=30)
        period_name = "So‘nggi 30 kun"
    else:
        start_date = None
        period_name = "Barcha davr"

    stats = await get_dashboard_statistics(session, start_date=start_date)
    text = format_stats_text(stats, period_name)

    try:
        await callback.message.edit_text(text, reply_markup=get_statistics_menu(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "stats_export:excel")
async def export_excel_report(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    await callback.answer("Excel hisobot tayyorlanmoqda, iltimos kuting...")
    
    try:
        file_path = await generate_appeals_excel_report(session)
        doc = FSInputFile(file_path, filename=f"Aniq_fanlar_Murojaatlar_Hisoboti_{datetime.now().strftime('%Y_%m_%d')}.xlsx")
        
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=doc,
            caption="📊 <b>Gumanitar fanlar va jismoniy madaniyat fakulteti elektron murojaatlarining to‘liq Excel hisoboti.</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error generating Excel report: {e}", exc_info=True)
        await callback.message.answer("❌ Excel hisobotini shakllantirishda xatolik yuz berdi.")


# ==================== BROADCAST / XABAR YUBORISH ====================

@router.callback_query(F.data == "admin_nav:broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📢 <b>FOYDALANUVCHILARGA XABAR YUBORISH (E'LON)</b>\n\n"
        "Barcha bot foydalanuvchilariga yuboriladigan e'lon yoki bildirishnoma matnini kiriting:\n\n"
        "Bekor qilish uchun '❌ Bekor qilish' deb yozing.",
        parse_mode="HTML"
    )
    await state.set_state(AdminBroadcastState.waiting_message)
    await callback.answer()


@router.message(AdminBroadcastState.waiting_message, F.text)
async def process_broadcast_message(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(broadcast_text=text)

    buttons = [
        [InlineKeyboardButton(text="✅ Ha, hammaga yuborilsin", callback_data="broadcast_confirm:yes")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_nav:menu")]
    ]
    await message.answer(
        f"📢 <b>XABARNI TASDIQLASH:</b>\n\n{text}\n\nUshbu xabar barcha ro‘yxatdan o‘tgan foydalanuvchilarga yuborilsinmi?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await state.set_state(AdminBroadcastState.confirm_send)


@router.callback_query(AdminBroadcastState.confirm_send, F.data == "broadcast_confirm:yes")
async def execute_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    text = data.get("broadcast_text", "")

    # Fetch all registered users
    stmt = select(User.telegram_id).where(User.is_registered == True, User.is_active == True)
    res = await session.execute(stmt)
    tg_ids = list(res.scalars().all())

    sent_count = 0
    fail_count = 0

    await callback.message.edit_text(f"⏳ Xabar {len(tg_ids)} ta foydalanuvchiga yuborilmoqda...")

    for tg_id in tg_ids:
        try:
            await bot.send_message(
                chat_id=tg_id,
                text=f"📢 <b>GUMANITAR FANLAR VA JISMONIY MADANIYAT FAKULTETIDAN BILDIRISHNOMA:</b>\n\n{text}",
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception:
            fail_count += 1

    await state.clear()
    await callback.message.answer(
        f"✅ <b>E'lon muvaffaqiyatli tarqatildi!</b>\n\n"
        f"• Yetkazildi: <b>{sent_count} ta</b>\n"
        f"• Yetkazilmadi (bloklangan): <b>{fail_count} ta</b>",
        parse_mode="HTML"
    )
    await callback.answer()

