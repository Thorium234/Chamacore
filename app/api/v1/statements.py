"""PDF statement download endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.statement import StatementService
from app.services.statement_pdf import render_statement_pdf

router = APIRouter(tags=["statements"])

PDF_MEDIA_TYPE = "application/pdf"


@router.get("/chamas/{chama_id}/statements")
def download_statement(
    chama_id: uuid.UUID,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    membership_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Download a statement for a date range as a PDF file.

    Chama-wide for CHAIRPERSON, TREASURER and PLATFORM_ADMIN. Any other active
    member receives their own statement only. The response is a file, not JSON,
    so the client performs a blob download (frontend plan F7).
    """
    statement = StatementService(db).build(
        actor=actor,
        chama_id=chama_id,
        date_from=date_from,
        date_to=date_to,
        membership_id=membership_id,
    )
    pdf = render_statement_pdf(statement)
    filename = f"statement-{chama_id}-{statement.period_from}-{statement.period_to}.pdf"
    return Response(
        content=pdf,
        media_type=PDF_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf)),
        },
    )
