"""Server-side PDF rendering for Chama statements.

Rendering lives on the server so the client only downloads a blob (frontend
plan F7). Uses reportlab's platypus flowables for automatic pagination.
"""

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.statement import ContributionLine, Statement, StatementLine

ACCENT = colors.HexColor("#1F3A5F")
MUTED = colors.HexColor("#6B7280")
RULE = colors.HexColor("#D1D5DB")


def _money(value: Decimal, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "StmtTitle",
            parent=base["Title"],
            fontSize=18,
            leading=22,
            textColor=ACCENT,
            alignment=0,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "StmtSubtitle",
            parent=base["Normal"],
            fontSize=9,
            leading=13,
            textColor=MUTED,
        ),
        "section": ParagraphStyle(
            "StmtSection",
            parent=base["Heading2"],
            fontSize=11,
            leading=15,
            textColor=ACCENT,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "StmtCell", parent=base["Normal"], fontSize=8, leading=10
        ),
        "amount": ParagraphStyle(
            "StmtAmount",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
        ),
        "total": ParagraphStyle(
            "StmtTotal",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=ACCENT,
        ),
    }


def _table(
    data: list[list],
    col_widths: list[float],
    styles: dict[str, ParagraphStyle],
    *,
    numeric_columns: tuple[int, ...] = (),
) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    commands: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.25, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
    ]
    for column in numeric_columns:
        commands.append(("ALIGN", (column, 1), (column, -1), "RIGHT"))
    table.setStyle(TableStyle(commands))
    return table


def _contribution_rows(
    contributions: list[ContributionLine], currency: str, styles: dict[str, ParagraphStyle]
) -> list[list]:
    rows = [
        [
            Paragraph("Period", styles["cell"]),
            Paragraph("Paid on", styles["cell"]),
            Paragraph("Amount", styles["amount"]),
            Paragraph("Share units", styles["amount"]),
        ]
    ]
    for item in contributions:
        rows.append(
            [
                Paragraph(item.period, styles["cell"]),
                Paragraph(item.paid_on.isoformat() if item.paid_on else "Not recorded", styles["cell"]),
                Paragraph(_money(item.amount, currency), styles["amount"]),
                Paragraph(f"{item.share_units:,.4f}", styles["amount"]),
            ]
        )
    return rows


def _ledger_rows(
    lines: list[StatementLine], currency: str, styles: dict[str, ParagraphStyle]
) -> list[list]:
    rows = [
        [
            Paragraph("Date", styles["cell"]),
            Paragraph("Ref", styles["cell"]),
            Paragraph("Description", styles["cell"]),
            Paragraph("Debit", styles["amount"]),
            Paragraph("Credit", styles["amount"]),
            Paragraph("Balance", styles["amount"]),
        ]
    ]
    for line in lines:
        rows.append(
            [
                Paragraph(line.posted_on.isoformat() if line.posted_on else "-", styles["cell"]),
                Paragraph(line.reference, styles["cell"]),
                Paragraph(line.description, styles["cell"]),
                Paragraph(_money(line.debit, currency) if line.debit else "-", styles["amount"]),
                Paragraph(_money(line.credit, currency) if line.credit else "-", styles["amount"]),
                Paragraph(_money(line.running_balance, currency), styles["amount"]),
            ]
        )
    return rows


def render_statement_pdf(statement: Statement) -> bytes:
    """Render a statement to PDF bytes.

    The document always contains a header, the period, and a summary. When the
    window holds no activity the tables are replaced with an explicit
    "no recorded activity" note rather than an empty table.
    """
    styles = _styles()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Statement {statement.chama_name}",
        author="ChamaCore",
    )

    story: list = [
        Paragraph("Statement of account", styles["title"]),
        Paragraph(statement.chama_name, styles["subtitle"]),
        Spacer(1, 6),
    ]

    meta = [
        ["Statement type", statement.scope_label],
        ["Member", statement.member_name or "All members"],
        [
            "Membership number",
            str(statement.member_number) if statement.member_number is not None else "-",
        ],
        ["Period", f"{statement.period_from.isoformat()} to {statement.period_to.isoformat()}"],
        ["Currency", statement.currency],
        ["Chama status", statement.chama_status],
        ["Generated at", statement.generated_at],
    ]
    meta_table = Table(meta, colWidths=[45 * mm, 110 * mm], hAlign="LEFT")
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, RULE),
                ("LINEABOVE", (0, -1), (-1, -1), 0.5, RULE),
            ]
        )
    )
    story.append(meta_table)

    story.append(Paragraph("Confirmed contributions", styles["section"]))
    if statement.contributions:
        story.append(
            _table(
                _contribution_rows(statement.contributions, statement.currency, styles),
                [35 * mm, 32 * mm, 45 * mm, 45 * mm],
                styles,
                numeric_columns=(2, 3),
            )
        )
    else:
        story.append(Paragraph("No confirmed contributions in this period.", styles["subtitle"]))

    story.append(Paragraph("Ledger activity", styles["section"]))
    if statement.lines:
        story.append(
            _table(
                _ledger_rows(statement.lines, statement.currency, styles),
                [22 * mm, 18 * mm, 58 * mm, 27 * mm, 27 * mm, 30 * mm],
                styles,
                numeric_columns=(3, 4, 5),
            )
        )
        story.append(Spacer(1, 6))
        totals = [
            ["", "", "Totals", _money(statement.total_debit, statement.currency),
             _money(statement.total_credit, statement.currency),
             _money(statement.closing_balance, statement.currency)]
        ]
        totals_table = Table(totals, colWidths=[22 * mm, 18 * mm, 58 * mm, 27 * mm, 27 * mm, 30 * mm], hAlign="LEFT")
        totals_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), ACCENT),
                    ("ALIGN", (3, 0), (-1, 0), "RIGHT"),
                    ("LINEABOVE", (0, 0), (-1, 0), 0.75, ACCENT),
                    ("TOPPADDING", (0, 0), (-1, 0), 5),
                ]
            )
        )
        story.append(totals_table)
    else:
        story.append(Paragraph("No ledger activity in this period.", styles["subtitle"]))

    story.append(PageBreak())
    story.append(Paragraph("Basis of this statement", styles["section"]))
    story.append(
        Paragraph(
            "Figures are derived from confirmed contribution records and from "
            "posted double-entry ledger transactions belonging to this Chama. "
            "Pending contributions are excluded because they are not yet "
            "financial facts, and reversed contributions are excluded because "
            "they have already been unwound by a compensating entry. The ledger "
            "is the authoritative financial record; this document is a read-only "
            "projection of it and is not itself a financial record.",
            styles["subtitle"],
        )
    )

    document.build(story)
    return buffer.getvalue()
