import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from config import settings
from database.models import Base, AppealTopic, SystemSetting, User, UserRole

logger = logging.getLogger(__name__)

# Initialize engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.LOG_LEVEL.upper() == "DEBUG"),
    future=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initializes tables and seeds necessary default records."""
    logger.info("Initializing database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed default data
    async with AsyncSessionLocal() as session:
        try:
            # 1. Seed Topics
            existing_topics = await session.execute(select(AppealTopic))
            if not existing_topics.scalars().first():
                default_topics = [
                    "Ta'lim jarayoni",
                    "Dars mashg‘ulotlari",
                    "Dars jadvali",
                    "O‘quv dasturlari",
                    "Imtihon va baholash",
                    "O‘qituvchilar faoliyati",
                    "Talabalar bilan ishlash",
                    "Ilmiy va akademik faoliyat",
                    "Fakultet va kafedralar faoliyati",
                    "Hujjatlar va ma'lumotnomalar",
                    "Boshqa masalalar"
                ]
                for idx, topic_name in enumerate(default_topics, start=1):
                    session.add(AppealTopic(name=topic_name, order_num=idx, is_active=True))
                logger.info(f"Seeded {len(default_topics)} default appeal topics.")

            # 2. Seed System Settings
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
            
            for key, val in default_settings.items():
                setting_res = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
                existing_setting = setting_res.scalar_one_or_none()
                if not existing_setting:
                    session.add(SystemSetting(key=key, value=val))
                elif key in ["dekan_name", "department_name", "contact_phone", "contact_email", "reception_hours"]:
                    # Keep synced with exact details
                    existing_setting.value = val
            
            # 3. Seed Super Admin
            if settings.SUPER_ADMIN_ID and settings.SUPER_ADMIN_ID > 0:
                admin_res = await session.execute(
                    select(User).where(User.telegram_id == settings.SUPER_ADMIN_ID)
                )
                admin_user = admin_res.scalar_one_or_none()
                if not admin_user:
                    admin_user = User(
                        telegram_id=settings.SUPER_ADMIN_ID,
                        full_name="Bosh Administrator",
                        phone="+998000000000",
                        user_type="XODIM",
                        role=UserRole.SUPER_ADMIN.value,
                        is_active=True,
                        is_registered=True
                    )
                    session.add(admin_user)
                    logger.info(f"Created Super Admin with Telegram ID: {settings.SUPER_ADMIN_ID}")
                elif admin_user.role != UserRole.SUPER_ADMIN.value:
                    admin_user.role = UserRole.SUPER_ADMIN.value
                    logger.info(f"Upgraded user {settings.SUPER_ADMIN_ID} to Super Admin role.")

            # 4. Seed Dekan
            if settings.DEKAN_ID and settings.DEKAN_ID > 0:
                dekan_res = await session.execute(
                    select(User).where(User.telegram_id == settings.DEKAN_ID)
                )
                dekan_user = dekan_res.scalar_one_or_none()
                if not dekan_user:
                    dekan_user = User(
                        telegram_id=settings.DEKAN_ID,
                        full_name="Komilov Jamoliddin Karimjonovich",
                        phone="+998672251020",
                        user_type="XODIM",
                        role=UserRole.DEKAN.value,
                        staff_position="Gumanitar fanlar va jismoniy madaniyat fakulteti dekani",
                        is_active=True,
                        is_registered=True
                    )
                    session.add(dekan_user)
                    logger.info(f"Created Dekan with Telegram ID: {settings.DEKAN_ID}")
                else:
                    dekan_user.role = UserRole.DEKAN.value
                    dekan_user.staff_position = "Gumanitar fanlar va jismoniy madaniyat fakulteti dekani"
                    dekan_user.full_name = "Komilov Jamoliddin Karimjonovich"
                    dekan_user.phone = "+998672251020"
                    logger.info(f"Upgraded user {settings.DEKAN_ID} to Dekan role.")

            await session.commit()
            logger.info("Database initialized successfully.")
        except Exception as e:
            await session.rollback()
            logger.error(f"Error during database initialization: {e}", exc_info=True)
            raise

