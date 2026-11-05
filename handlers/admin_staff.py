import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.models import User, UserRole
from database.queries import get_or_create_user, get_all_staff_members
from states.admin import AdminStaffManageState
from utils.helpers import log_audit, normalize_phone

logger = logging.getLogger(__name__)
router = Router(name="admin_staff_router")


@router.callback_query(F.data == "admin_nav:staff")
async def show_staff_management(callback: CallbackQuery, session: AsyncSession):
    user = await get_or_create_user(session, callback.from_user.id)
    is_super = (settings.SUPER_ADMIN_ID and callback.from_user.id == settings.SUPER_ADMIN_ID) or user.role == UserRole.SUPER_ADMIN.value
    is_dekan = user.role == UserRole.DEKAN.value

    if not (is_super or is_dekan):
        await callback.answer("Ushbu bo‘lim faqat Dekan va Bosh administrator uchun!", show_alert=True)
        return

    staff_list = await get_all_staff_members(session)

    text_lines = [
        "👥 <b>FAKULTET XODIMLARI VA MAS'ULLARINI BOSHQARISH</b>\n",
        f"Jami xodimlar: <b>{len(staff_list)} nafar</b>\n"
    ]

    buttons = []
    for s in staff_list:
        role_label = UserRole.label(s.role)
        pos = f" ({s.staff_position})" if s.staff_position else ""
        text_lines.append(f"• <b>{s.full_name}</b>{pos} — <i>{role_label}</i> (ID: <code>{s.telegram_id}</code>)")
        buttons.append([
            InlineKeyboardButton(
                text=f"⚙️ {s.full_name} - {role_label}",
                callback_data=f"staff_edit:{s.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="➕ Yangi xodim qo‘shish", callback_data="staff_add")])
    buttons.append([InlineKeyboardButton(text="🏠 Admin menyu", callback_data="admin_nav:menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("\n".join(text_lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "staff_add")
async def add_staff_step1(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>YANGI XODIM QO‘SHISH</b>\n\n"
        "Yangi xodimning <b>Telegram ID</b> raqamini kiriting:\n"
        "<i>(Xodim Telegram ID raqamini @userinfobot orqali bilib olishi mumkin)</i>\n\n"
        "Bekor qilish uchun '❌ Bekor qilish' deb yozing.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStaffManageState.waiting_tg_id)
    await callback.answer()


@router.message(AdminStaffManageState.waiting_tg_id, F.text)
async def add_staff_step2(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip()
    if not text_val.isdigit():
        await message.answer("Telegram ID faqat raqamlardan iborat bo‘lishi kerak. Qaytadan kiriting:")
        return

    tg_id = int(text_val)
    # Check if user already exists
    stmt = select(User).where(User.telegram_id == tg_id)
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()

    await state.update_data(new_staff_tg_id=tg_id)

    if existing:
        await state.update_data(new_staff_full_name=existing.full_name, new_staff_phone=existing.phone)
        # Select role directly
        buttons = [
            [InlineKeyboardButton(text="🏛 Dekan", callback_data="new_role:DEKAN")],
            [InlineKeyboardButton(text="⚙️ Administrator", callback_data="new_role:ADMINISTRATOR")],
            [InlineKeyboardButton(text="👤 Mas'ul xodim", callback_data="new_role:MASUL_XODIM")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_nav:staff")]
        ]
        await message.answer(
            f"Foydalanuvchi tizimda mavjud: <b>{existing.full_name}</b>\nUshbu xodimga qanday rol bermoqchisiz?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
        await state.set_state(AdminStaffManageState.waiting_role)
    else:
        await message.answer("Xodimning to‘liq F.I.Sh.ini kiriting:")
        await state.set_state(AdminStaffManageState.waiting_full_name)


@router.message(AdminStaffManageState.waiting_full_name, F.text)
async def add_staff_step3(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 4:
        await message.answer("F.I.Sh. to‘liq kiritilishi kerak:")
        return
    await state.update_data(new_staff_full_name=name)
    await message.answer("Xodimning telefon raqamini kiriting (+998901234567):")
    await state.set_state(AdminStaffManageState.waiting_phone)


@router.message(AdminStaffManageState.waiting_phone, F.text)
async def add_staff_step4(message: Message, state: FSMContext):
    phone = normalize_phone(message.text.strip())
    if not phone:
        await message.answer("Telefon raqami noto‘g‘ri (+998901234567 formatida):")
        return
    await state.update_data(new_staff_phone=phone)

    buttons = [
        [InlineKeyboardButton(text="🏛 Dekan", callback_data="new_role:DEKAN")],
        [InlineKeyboardButton(text="⚙️ Administrator", callback_data="new_role:ADMINISTRATOR")],
        [InlineKeyboardButton(text="👤 Mas'ul xodim", callback_data="new_role:MASUL_XODIM")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_nav:staff")]
    ]
    await message.answer(
        "Xodimga beriladigan rolni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(AdminStaffManageState.waiting_role)


@router.callback_query(AdminStaffManageState.waiting_role, F.data.startswith("new_role:"))
async def add_staff_step5_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split(":")[1]
    await state.update_data(new_staff_role=role)
    await callback.message.edit_text(
        f"Rol: <b>{UserRole.label(role)}</b>\n\n"
        "Xodimning lavozimini kiriting (Masalan: Dekan o‘rinbosari, Kafedra mudiri, Dotsent, Katta o‘qituvchi):",
        parse_mode="HTML"
    )
    await state.set_state(AdminStaffManageState.waiting_position)
    await callback.answer()


@router.message(AdminStaffManageState.waiting_position, F.text)
async def add_staff_step6_finish(message: Message, state: FSMContext, session: AsyncSession):
    position = message.text.strip()
    data = await state.get_data()
    tg_id = data.get("new_staff_tg_id")
    full_name = data.get("new_staff_full_name", "Fakultet xodimi")
    phone = data.get("new_staff_phone", "+998000000000")
    role = data.get("new_staff_role", UserRole.MASUL_XODIM.value)

    if not tg_id:
        await message.answer("Xatolik: Xodim Telegram ID topilmadi. Boshidan urinib ko'ring.")
        await state.clear()
        return

    current_user = await get_or_create_user(session, message.from_user.id)

    try:
        # Check if user already in DB
        res = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = res.scalar_one_or_none()
        if user:
            user.role = role
            user.staff_position = position
            user.is_active = True
            if full_name and user.full_name in ["Foydalanuvchi", "", None]:
                user.full_name = full_name
            if phone and (not user.phone or user.phone == "+998000000000"):
                user.phone = phone
        else:
            user = User(
                telegram_id=tg_id,
                full_name=full_name,
                phone=phone,
                role=role,
                staff_position=position,
                user_type="XODIM",
                is_active=True,
                is_registered=True
            )
            session.add(user)

        await log_audit(
            session=session,
            user_id=current_user.id,
            telegram_id=current_user.telegram_id,
            action="ADD_STAFF",
            target_type="User",
            target_id=str(tg_id),
            details=f"Xodim tayinlandi: {full_name}, rol: {role}, lavozim: {position}"
        )

        await session.commit()
        await state.clear()

        # Send notification to the newly appointed staff member if possible
        try:
            await message.bot.send_message(
                chat_id=tg_id,
                text=(
                    f"🎉 <b>Hurmatli {full_name}!</b>\n\n"
                    f"Sizga <b>Gumanitar fanlar va jismoniy madaniyat fakulteti</b> elektron murojaatlar axborot tizimida xodimlik vakolati berildi:\n"
                    f"• <b>Rol:</b> {UserRole.label(role)}\n"
                    f"• <b>Lavozim:</b> {position}\n\n"
                    f"Tizimga kirish uchun /start yoki /admin buyrug‘ini bosing."
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

        buttons = [
            [InlineKeyboardButton(text="👥 Xodimlar ro‘yxati", callback_data="admin_nav:staff")],
            [InlineKeyboardButton(text="🏠 Admin menyu", callback_data="admin_nav:menu")]
        ]
        await message.answer(
            f"✅ <b>Xodim muvaffaqiyatli tayinlandi!</b>\n\n"
            f"<b>F.I.Sh:</b> {full_name}\n"
            f"<b>Rol:</b> {UserRole.label(role)}\n"
            f"<b>Lavozim:</b> {position}\n"
            f"<b>Telegram ID:</b> <code>{tg_id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error while adding staff: {e}", exc_info=True)
        await session.rollback()
        await message.answer(f"❌ Xodimni saqlashda xatolik yuz berdi: {e}")


@router.callback_query(F.data.startswith("staff_edit:"))
async def edit_staff_view(callback: CallbackQuery, session: AsyncSession):
    staff_id = int(callback.data.split(":")[1])
    staff = (await session.execute(select(User).where(User.id == staff_id))).scalar_one_or_none()
    if not staff:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    text = (
        f"👤 <b>XODIM MA'LUMOTLARI:</b>\n\n"
        f"<b>F.I.Sh:</b> {staff.full_name}\n"
        f"<b>Lavozimi:</b> {staff.staff_position or '-'}\n"
        f"<b>Roli:</b> {UserRole.label(staff.role)}\n"
        f"<b>Telefon:</b> {staff.phone}\n"
        f"<b>Telegram ID:</b> <code>{staff.telegram_id}</code>\n"
    )

    buttons = [
        [InlineKeyboardButton(text="🔄 Rolni o‘zgartirish", callback_data=f"staff_changerole:{staff.id}")],
        [InlineKeyboardButton(text="❌ Vakolatni bekor qilish", callback_data=f"staff_remove:{staff.id}")],
        [InlineKeyboardButton(text="⬅️ Xodimlar ro‘yxatiga", callback_data="admin_nav:staff")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("staff_remove:"))
async def remove_staff_confirm(callback: CallbackQuery, session: AsyncSession):
    staff_id = int(callback.data.split(":")[1])
    staff = (await session.execute(select(User).where(User.id == staff_id))).scalar_one_or_none()
    current_user = await get_or_create_user(session, callback.from_user.id)

    if not staff:
        await callback.answer("Xodim topilmadi!", show_alert=True)
        return

    staff.role = UserRole.USER.value
    staff.staff_position = None

    await log_audit(
        session=session,
        user_id=current_user.id,
        telegram_id=current_user.telegram_id,
        action="REMOVE_STAFF",
        target_type="User",
        target_id=str(staff.id),
        details=f"Xodim vakolati bekor qilindi: {staff.full_name}"
    )

    await session.commit()
    await callback.answer("Xodim vakolati bekor qilindi!", show_alert=True)
    # Return to staff list
    await show_staff_management(callback, session)

