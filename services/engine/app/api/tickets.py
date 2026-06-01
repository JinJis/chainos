"""Need-Fact ticket inbox + source attachment."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from ..db import session_scope
from ..models import NeedFactTicket, Source
from ..schemas import SourceOut, TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _to_out(t: NeedFactTicket) -> TicketOut:
    out = TicketOut.model_validate(t)
    out.source_count = len(t.sources)
    return out


@router.get("", response_model=list[TicketOut])
def list_tickets(theme_id: str | None = None, status: str | None = None) -> list[TicketOut]:
    with session_scope() as s:
        stmt = select(NeedFactTicket).order_by(
            NeedFactTicket.priority, NeedFactTicket.created_at
        )
        if theme_id:
            stmt = stmt.where(NeedFactTicket.theme_id == theme_id)
        if status:
            stmt = stmt.where(NeedFactTicket.status == status)
        return [_to_out(t) for t in s.scalars(stmt).all()]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str) -> TicketOut:
    with session_scope() as s:
        t = s.get(NeedFactTicket, ticket_id)
        if t is None:
            raise HTTPException(404, "ticket not found")
        return _to_out(t)


@router.post("/{ticket_id}/attach", response_model=SourceOut)
async def attach_source(
    ticket_id: str,
    type: str = Form("filing"),
    publisher: str = Form(""),
    url: str = Form(""),
    as_of_date: str = Form(""),
    confidence: str = Form("verified"),
    content_text: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> SourceOut:
    """Admin uploads filing/IR evidence to a ticket. M2 runs MEDIUM/LOW parse on it."""
    filename = None
    text = content_text
    if file is not None:
        filename = file.filename
        raw = await file.read()
        try:
            text = (text or "") + "\n" + raw.decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            pass
    with session_scope() as s:
        ticket = s.get(NeedFactTicket, ticket_id)
        if ticket is None:
            raise HTTPException(404, "ticket not found")
        src = Source(
            theme_id=ticket.theme_id,
            ticket_id=ticket_id,
            type=type,
            publisher=publisher,
            url=url,
            as_of_date=as_of_date,
            confidence=confidence,
            filename=filename,
            content_text=text,
        )
        s.add(src)
        s.flush()
        return SourceOut.model_validate(src)
