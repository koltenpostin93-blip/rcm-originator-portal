"""Excel/PDF export helpers for summary tables."""
import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RCM_GREEN = colors.HexColor("#347A0C")


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Summary") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def summary_to_pdf_bytes(title: str, subtitle: str, df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    # Landscape so wider tables (e.g. the full purchase list, 10 columns) don't
    # overflow the page width.
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), title=title,
                             leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.textColor = RCM_GREEN
    cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8, leading=10)
    header_style = ParagraphStyle("header", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold")

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
        display_df = display_df.astype(str)

        # Wrap every cell in a Paragraph so long values wrap within a fixed
        # column width instead of overflowing off the page.
        header_row = [Paragraph(str(c), header_style) for c in display_df.columns]
        body_rows = [[Paragraph(v, cell_style) for v in row] for row in display_df.values.tolist()]
        data = [header_row] + body_rows

        col_width = doc.width / len(display_df.columns)
        table = Table(data, repeatRows=1, colWidths=[col_width] * len(display_df.columns))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), RCM_GREEN),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F2ED")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
