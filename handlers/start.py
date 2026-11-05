import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.models import User, UserRole, SystemSetting
from database.queries import get_or_create_user
from keyboards.main import get_main_menu_keyboard
from keyboards.user import get_user_type_keyboard
from states.registration import RegistrationState
from utils.helpers import get_setting

logger = logging.getLogger(__name__)
router = Router(name="start_router")


WELCOME_TEXT = """Assalomu alaykum!

PEDAGOGIKA FAKULTETINING elektron murojaatlar Telegram botiga xush kelibsiz!

Ushbu bot orqali Siz fakultet faoliyatiga oid ariza, shikoyat, taklif va savollaringizni yuborishingiz mumkin.

Har bir murojaatingiz maxsus raqam bilan ro‘yxatga olinadi va vakolatli mas'ullar tomonidan ko‘rib chiqiladi.

Murojaatingiz holatini kuzatish va fakultet dekanati bilan elektron muloqot qilish imkoniyati ham mavjud.

Marhamat, kerakli bo‘limni tanlang."""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    tg_user = message.from_user
    
    user = await get_or_create_user(
        session=session,
        tg_id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name or "Foydalanuvchi"
    )

    is_super = (settings.SUPER_ADMIN_ID and tg_user.id == settings.SUPER_ADMIN_ID) or user.role == UserRole.SUPER_ADMIN.value
    is_dekan = (settings.DEKAN_ID and tg_user.id == settings.DEKAN_ID) or user.role == UserRole.DEKAN.value
    is_admin = user.role == UserRole.ADMINISTRATOR.value
    is_staff = user.role == UserRole.MASUL_XODIM.value

    is_any_staff = is_super or is_dekan or is_admin or is_staff

    # Bot adminlari / dekan / mas'ullar uchun to'g'ridan-to'g'ri Admin panel ochiladi
    if is_any_staff:
        from handlers.admin import cmd_admin
        await cmd_admin(message, state, session)
        return

    # Qolgan oddiy foydalanuvchilar uchun esa oddiy murojaat oynasi
    # Agar foydalanuvchi hali ro'yxatdan o'tmagan bo'lsa, ro'yxatdan o'tish taklif qilinadi
    if not user.is_registered:
        reg_intro = (
            f"{WELCOME_TEXT}\n\n"
            "⚠️ <b>Murojaat yuborishdan avval bir marta ro‘yxatdan o‘tishingiz lozim.</b>\n"
            "Iltimos, o‘zingizga mos toifani tanlang:"
        )
        await message.answer(reg_intro, reply_markup=get_user_type_keyboard(), parse_mode="HTML")
        await state.set_state(RegistrationState.choosing_user_type)
        return

    # Ro'yxatdan o'tgan oddiy foydalanuvchiga oddiy murojaat bosh menyusi ko'rsatiladi
    await message.answer(
        WELCOME_TEXT,
        reply_markup=get_main_menu_keyboard(is_staff=False),
        parse_mode="HTML"
    )


@router.message(F.text == "❌ Bekor qilish")
async def process_cancel(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    user = await get_or_create_user(session, message.from_user.id)
    is_staff = user.role in [UserRole.SUPER_ADMIN.value, UserRole.DEKAN.value, UserRole.ADMINISTRATOR.value, UserRole.MASUL_XODIM.value]
    await message.answer(
        "Amal bekor qilindi. Bosh menyudasiz.",
        reply_markup=get_main_menu_keyboard(is_staff=is_staff)
    )


@router.message(F.text.contains("Bog‘lanish") | F.text.contains("Bog'lanish"))
async def process_contact(message: Message, session: AsyncSession):
    dept_name = await get_setting(session, "department_name", "Pedagogika fakulteti")
    inst_name = await get_setting(session, "institute_name", "Guliston davlat pedagogika instituti")
    phone = await get_setting(session, "contact_phone", "+998 99 460-05-20")
    email = await get_setting(session, "contact_email", "norqulovshavkat78@gmail.com")
    hours = await get_setting(session, "reception_hours", "Har kun: 09:00-17:00")
    dekan = await get_setting(session, "dekan_name", "Norqulov Shovkat Turg'unboyevich")

    text = (
        f"📞 <b>BOG‘LANISH VA ALOQA MA'LUMOTLARI</b>\n\n"
        f"🏛 <b>Muassasa:</b> {inst_name}\n"
        f"📚 <b>Fakultet:</b> {dept_name}\n"
        f"👤 <b>Fakultet dekani:</b> {dekan}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"✉️ <b>Elektron pochta:</b> {email}\n"
        f"🕒 <b>Qabul kunlari:</b> {hours}\n"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text.contains("Bot haqida"))
async def process_about(message: Message, session: AsyncSession):
    dept_name = await get_setting(session, "department_name", "Pedagogika fakulteti")
    text = (
        f"ℹ️ <b>BOT HAQIDA</b>\n\n"
        f"<b>E-MUROJAAT</b> — {dept_name} uchun mo‘ljallangan professional elektron murojaatlar axborot tizimi.\n\n"
        f"<b>Tizimning asosiy imkoniyatlari:</b>\n"
        f"• Ariza, shikoyat, taklif va savollarni onlayn yuborish\n"
        f"• Har bir murojaatga noyob raqam berish va monitoring qilish\n"
        f"• Ko‘rib chiqish muddatlari va mas'ullar ijrosini nazorat qilish\n"
        f"• Fakultet dekanati bilan to‘g‘ridan-to‘g‘ri elektron yozishmalar\n"
        f"• Shaxsiy ma'lumotlar va maxfiy murojaatlarning qat'iy xavfsizligi\n\n"
        f"<i>Versiya: 2.0 (2026)\nPedagogika fakulteti axborot xizmati.</i>"
    )
    await message.answer(text, parse_mode="HTML")

