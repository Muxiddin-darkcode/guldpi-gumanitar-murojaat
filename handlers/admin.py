import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.models import User, UserRole, AppealStatus
from database.queries import (
    get_or_create_user, get_admin_appeals_paginated,
    get_dashboard_statistics
)
from filters.admin_filter import IsStaffFilter
from keyboards.admin import get_admin_main_menu, get_appeals_pagination
from keyboards.main import get_main_menu_keyboard
from keyboards.staff import get_staff_assigned_keyboard

logger = logging.getLogger(__name__)
router = Router(name="admin_main_router")


@router.message(Command("admin"))
@router.message(F.text.contains("Boshqaruv paneli"))
async def cmd_admin(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    tg_id = message.from_user.id
    user = await get_or_create_user(session, tg_id)

    # Permission check
    is_super = (settings.SUPER_ADMIN_ID and tg_id == settings.SUPER_ADMIN_ID) or user.role == UserRole.SUPER_ADMIN.value
    is_dekan = (settings.DEKAN_ID and tg_id == settings.DEKAN_ID) or user.role == UserRole.DEKAN.value
    is_admin = user.role == UserRole.ADMINISTRATOR.value
    is_staff = user.role == UserRole.MASUL_XODIM.value

    if not (is_super or is_dekan or is_admin or is_staff):
        await message.answer("❌ Ushbu bo‘lim faqat Gumanitar fanlar va jismoniy madaniyat fakulteti mas'ul xodimlari va administratorlar uchun ochiq!")
        return

    # Close bottom reply keyboard when admin inline panel opens
    try:
        temp = await message.answer("⚡️", reply_markup=ReplyKeyboardRemove())
        await temp.delete()
    except Exception:
        pass

    # If user is only a Mas'ul Xodim (responsible staff), show their dedicated dashboard
    if is_staff and not (is_super or is_dekan or is_admin):
        appeals, total = await get_admin_appeals_paginated(
            session=session,
            assigned_to_id=user.id,
            page=1,
            limit=5
        )
        kb = get_staff_assigned_keyboard(appeals, current_page=1, total_count=total, limit=5)
        await message.answer(
            f"👤 <b>MAS'UL XODIM KABINETI: {user.full_name}</b>\n\n"
            f"Sizga biriktirilgan murojaatlar soni: <b>{total} ta</b>\n"
            "Ko‘rib chiqish uchun ro‘yxatdan tanlang:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    # Admin / Dekan / Super Admin Dashboard
    stats = await get_dashboard_statistics(session)
    role_label = UserRole.label(user.role)

    text = (
        f"⚡️ <b>GUMANITAR FANLAR VA JISMONIY MADANIYAT FAKULTETI | ADMIN BOSHQARUV PANELI</b>\n\n"
        f"👤 <b>Mas'ul:</b> {user.full_name} ({role_label})\n\n"
        f"<b>Murojaatlar umumiy holati:</b>\n"
        f"• 📥 Yangi: <b>{stats['yangi']} ta</b>\n"
        f"• 🔄 Ko‘rib chiqilmoqda: <b>{stats['korib_chiqilmoqda']} ta</b>\n"
        f"• ✅ Hal qilingan: <b>{stats['hal_qilindi']} ta</b>\n"
        f"• ❌ Rad etilgan: <b>{stats['rad_etildi']} ta</b>\n"
        f"• ⏳ Muddati o‘tgan: <b>{stats['overdue']} ta</b>\n"
        f"• 📊 Jami murojaatlar: <b>{stats['total']} ta</b>\n\n"
        "Kerakli bo‘limni tanlang:"
    )

    kb = get_admin_main_menu(is_super_admin=is_super, is_dekan=is_dekan)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "admin_nav:menu")
async def nav_to_admin_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    tg_id = callback.from_user.id
    user = await get_or_create_user(session, tg_id)

    is_super = (settings.SUPER_ADMIN_ID and tg_id == settings.SUPER_ADMIN_ID) or user.role == UserRole.SUPER_ADMIN.value
    is_dekan = (settings.DEKAN_ID and tg_id == settings.DEKAN_ID) or user.role == UserRole.DEKAN.value

    stats = await get_dashboard_statistics(session)
    role_label = UserRole.label(user.role)

    text = (
        f"⚡️ <b>GUMANITAR FANLAR VA JISMONIY MADANIYAT FAKULTETI | ADMIN BOSHQARUV PANELI</b>\n\n"
        f"👤 <b>Mas'ul:</b> {user.full_name} ({role_label})\n\n"
        f"<b>Murojaatlar umumiy holati:</b>\n"
        f"• 📥 Yangi: <b>{stats['yangi']} ta</b>\n"
        f"• 🔄 Ko‘rib chiqilmoqda: <b>{stats['korib_chiqilmoqda']} ta</b>\n"
        f"• ✅ Hal qilingan: <b>{stats['hal_qilindi']} ta</b>\n"
        f"• ❌ Rad etilgan: <b>{stats['rad_etildi']} ta</b>\n"
        f"• ⏳ Muddati o‘tgan: <b>{stats['overdue']} ta</b>\n"
        f"• 📊 Jami murojaatlar: <b>{stats['total']} ta</b>\n\n"
        "Kerakli bo‘limni tanlang:"
    )

    kb = get_admin_main_menu(is_super_admin=is_super, is_dekan=is_dekan)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_nav:exit")
async def nav_exit_admin(callback: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, callback.from_user.id)
    is_staff = user.role in [
        UserRole.SUPER_ADMIN.value,
        UserRole.DEKAN.value,
        UserRole.ADMINISTRATOR.value,
        UserRole.MASUL_XODIM.value
    ]
    await callback.message.delete()
    await callback.message.answer(
        "Foydalanuvchi asosiy menyusiga qaytdingiz.",
        reply_markup=get_main_menu_keyboard(is_staff=is_staff)
    )
    await callback.answer()

