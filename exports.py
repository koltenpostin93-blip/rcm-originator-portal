"""Excel/PDF export helpers for summary tables."""
import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RCM_GREEN = colors.HexColor("#347A0C")


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Summary") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def summary_to_pdf_bytes(title: str, subtitle: str, df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=title)
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.textColor = RCM_GREEN

    elements = [
        Paragraph(title, title_style),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 16),
    ]

    if df.empty:
        elements.append(Paragraph("No data.", styles["Normal"]))
    else:
        display_df = df.copy()
        for col in display_df.columns:
            if pd.api.types.is_float_dtype(display_df[col]):
                display_df[col] = display_df[col].map(lambda v: f"{v:,.2f}")
            elif pd.api.types.is_integer_dtype(display_df[col]):
                display_df[col] = display_df[col].map(lambda v: f"{v:,}")

        data = [list(display_df.columns)] + display_df.astype(str).values.tolist()
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), RCM_GREEN),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F2ED")]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ]))
        elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
