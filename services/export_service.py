import os
from datetime import datetime, timezone
from typing import List, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from database.models import Appeal, AppealStatus, User, UserType
from utils.helpers import format_datetime, get_current_time


async def generate_appeals_excel_report(session: AsyncSession) -> str:
    """
    Generates a comprehensive Excel report of all appeals and statistics.
    Returns the file path of the generated Excel document.
    """
    os.makedirs("data/reports", exist_ok=True)
    timestamp = get_current_time().strftime("%Y%m%d_%H%M%S")
    file_path = f"data/reports/E_Murojaat_Hisobot_{timestamp}.xlsx"

    wb = openpyxl.Workbook()

    # Styling constants
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=11)
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # ==================== SHEET 1: RO'YXAT ====================
    ws_list = wb.active
    ws_list.title = "Murojaatlar ro'yxati"

    # Title block
    ws_list["A1"] = "GUMANITAR FANLAR VA JISMONIY MADANIYAT FAKULTETI - ELEKTRON MUROJAATLAR HISOBOTI"
    ws_list["A1"].font = title_font
    ws_list["A2"] = f"Shakllantirilgan sana: {format_datetime(datetime.now(timezone.utc))}"
    ws_list["A2"].font = regular_font

    headers = [
        "№", "Murojaat raqami", "Sana", "Murojaatchi F.I.Sh.", "Murojaatchi turi",
        "Telefon", "Murojaat turi", "Yo‘nalishi", "Mavzu", "Mazmuni",
        "Maxfiylik", "Holati", "Mas'ul xodim", "Ijro muddati", "Rasmiy javob"
    ]

    header_row = 4
    for col_idx, header in enumerate(headers, 1):
        cell = ws_list.cell(row=header_row, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Fetch appeals
    stmt = (
        select(Appeal)
        .options(
            selectinload(Appeal.applicant),
            selectinload(Appeal.assigned_to)
        )
        .order_by(desc(Appeal.created_at))
    )
    res = await session.execute(stmt)
    appeals: List[Appeal] = list(res.scalars().all())

    for idx, app in enumerate(appeals, 1):
        row = header_row + idx
        applicant = app.applicant
        assignee = app.assigned_to.full_name if app.assigned_to else "Biriktirilmagan"
        confidentiality = "Maxfiy" if app.is_confidential else "Oddiy"
        status_label = AppealStatus.label(app.status)

        row_data = [
            idx,
            app.appeal_number,
            format_datetime(app.created_at),
            applicant.full_name if applicant else "Noma'lum",
            UserType.label(applicant.user_type) if applicant else "-",
            applicant.phone if applicant else "-",
            app.appeal_type,
            app.topic_name,
            app.title,
            app.description,
            confidentiality,
            status_label,
            assignee,
            format_datetime(app.deadline) if app.deadline else "-",
            app.response_text or "-"
        ]

        for col_idx, val in enumerate(row_data, 1):
            cell = ws_list.cell(row=row, column=col_idx, value=val)
            cell.font = regular_font
            cell.border = thin_border
            if col_idx in [1, 2, 3, 5, 6, 7, 11, 12, 14]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)

    # Auto-adjust column widths
    for col in ws_list.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row < header_row:
                continue
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws_list.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    # ==================== SHEET 2: STATISTIKA ====================
    ws_stats = wb.create_sheet(title="Statistika xulosasi")
    ws_stats["A1"] = "UMUMIY STATISTIK KO'RSATKICHLAR"
    ws_stats["A1"].font = title_font

    stats_headers = ["Ko'rsatkich", "Soni"]
    for col_idx, h in enumerate(stats_headers, 1):
        c = ws_stats.cell(row=3, column=col_idx, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")

    total_apps = len(appeals)
    new_apps = sum(1 for a in appeals if a.status == AppealStatus.YANGI.value)
    in_progress = sum(1 for a in appeals if a.status in [AppealStatus.KORIB_CHIQILMOQDA.value, AppealStatus.BIRIKTIRILDI.value, AppealStatus.JAVOB_TAYYORLANMOQDA.value])
    resolved = sum(1 for a in appeals if a.status == AppealStatus.HAL_QILINDI.value)
    rejected = sum(1 for a in appeals if a.status == AppealStatus.RAD_ETILDI.value)

    students = sum(1 for a in appeals if a.applicant and a.applicant.user_type == UserType.TALABA.value)
    citizens = sum(1 for a in appeals if a.applicant and a.applicant.user_type == UserType.FUQARO.value)
    parents = sum(1 for a in appeals if a.applicant and a.applicant.user_type == UserType.OTA_ONA.value)

    stats_data = [
        ("Jami kelib tushgan murojaatlar", total_apps),
        ("Yangi murojaatlar", new_apps),
        ("Ko'rib chiqilayotgan / Ijrodagi", in_progress),
        ("Ijobiy hal etilganlar", resolved),
        ("Rad etilganlar", rejected),
        ("Talabalardan tushgan murojaatlar", students),
        ("Fuqarolardan tushgan murojaatlar", citizens),
        ("Ota-onalardan tushgan murojaatlar", parents),
    ]

    for idx, (label, val) in enumerate(stats_data, 1):
        r = 3 + idx
        c1 = ws_stats.cell(row=r, column=1, value=label)
        c2 = ws_stats.cell(row=r, column=2, value=val)
        c1.font = regular_font
        c1.border = thin_border
        c2.font = bold_font
        c2.border = thin_border
        c2.alignment = Alignment(horizontal="center", vertical="center")

    ws_stats.column_dimensions["A"].width = 40
    ws_stats.column_dimensions["B"].width = 15

    wb.save(file_path)
    return file_path

