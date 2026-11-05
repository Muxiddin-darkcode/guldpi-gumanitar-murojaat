from datetime import datetime
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import settings
from database.models import AppealSequence


async def generate_appeal_number(session: AsyncSession) -> str:
    """
    Generates a unique, non-repeating appeal number in format:
    AF-YYYY-XXXXXX (e.g. AF-2026-000001)
    Atomic and transaction-safe.
    """
    tz = pytz.timezone(settings.TIMEZONE)
    current_year = datetime.now(tz).year

    # Lock and update the sequence row
    result = await session.execute(
        select(AppealSequence)
        .where(AppealSequence.year == current_year)
        .with_for_update()
    )
    seq = result.scalar_one_or_none()

    if not seq:
        seq = AppealSequence(year=current_year, current_number=1)
        session.add(seq)
        current_num = 1
    else:
        seq.current_number += 1
        current_num = seq.current_number

    # Do not commit here, it commits with the appeal creation
    return f"{settings.APPEAL_PREFIX}-{current_year}-{current_num:06d}"

