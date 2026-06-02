"""Need-Fact ticket inbox + source attachment + evidence parse/approve."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from ..agent.extract import apply_lock, parse_evidence
from ..db import session_scope
from ..llm import Provider
from ..logging_config import get_logger
from ..models import NeedFactTicket, Source, Theme
from ..schemas import ApproveBody, ParsePreview, SourceOut, TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])
log = get_logger("api.tickets")


def _provider_for(theme: Theme | None) -> Provider | None:
    name = (theme.model_assignment or {}).get("MEDIUM") if theme else None
    return Provider(name) if name in ("anthropic", "google") else None


def _latest_source(ticket: NeedFactTicket) -> Source | None:
    sources = [s for s in ticket.sources if s.content_text]
    if not sources:
        return None
    return max(sources, key=lambda s: s.created_at)


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
        rows = [_to_out(t) for t in s.scalars(stmt).all()]
        log.debug(
            "list tickets",
            extra={"theme_id": theme_id, "status": status, "count": len(rows)},
        )
        return rows


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str) -> TicketOut:
    with session_scope() as s:
        t = s.get(NeedFactTicket, ticket_id)
        if t is None:
            log.warning("get_ticket: not found", extra={"ticket_id": ticket_id})
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
    log.info("attach evidence", extra={"ticket_id": ticket_id, "type": type, "has_file": file is not None})
    filename = None
    text = content_text
    if file is not None:
        filename = file.filename
        raw = await file.read()
        try:
            text = (text or "") + "\n" + raw.decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            log.warning("attach: could not decode upload", extra={"ticket_id": ticket_id})
    with session_scope() as s:
        ticket = s.get(NeedFactTicket, ticket_id)
        if ticket is None:
            log.warning("attach: ticket not found", extra={"ticket_id": ticket_id})
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


@router.post("/{ticket_id}/parse", response_model=ParsePreview)
def parse_ticket(ticket_id: str) -> ParsePreview:
    """MEDIUM/LOW parse of the latest uploaded evidence — preview only, no write."""
    log.info("parse ticket evidence", extra={"ticket_id": ticket_id})
    with session_scope() as s:
        ticket = s.get(NeedFactTicket, ticket_id)
        if ticket is None:
            log.warning("parse: ticket not found", extra={"ticket_id": ticket_id})
            raise HTTPException(404, "ticket not found")
        source = _latest_source(ticket)
        if source is None:
            log.warning("parse: no evidence uploaded", extra={"ticket_id": ticket_id})
            raise HTTPException(400, "no evidence uploaded to this ticket yet")
        theme = s.get(Theme, ticket.theme_id)
        field = (ticket.payload or {}).get("field", "value")
        preview = parse_evidence(
            content_text=source.content_text,
            field=field,
            provider=_provider_for(theme),
        )
        preview["source_id"] = source.id
        log.info("parse result", extra={"ticket_id": ticket_id, "field": field,
                                        "value": preview["value"], "found": preview["found"]})
        return ParsePreview(**preview)


@router.post("/{ticket_id}/approve")
def approve_ticket(ticket_id: str, body: ApproveBody) -> dict:
    """Approve the parse: lock the value + trust meta into Staging and resolve."""
    log.info("approve ticket", extra={"ticket_id": ticket_id, "override": body.value})
    with session_scope() as s:
        ticket = s.get(NeedFactTicket, ticket_id)
        if ticket is None:
            log.warning("approve: ticket not found", extra={"ticket_id": ticket_id})
            raise HTTPException(404, "ticket not found")
        source = _latest_source(ticket)
        if source is None:
            log.warning("approve: no evidence uploaded", extra={"ticket_id": ticket_id})
            raise HTTPException(400, "no evidence uploaded to this ticket yet")
        theme = s.get(Theme, ticket.theme_id)
        payload = ticket.payload or {}
        field = payload.get("field", "value")
        preview = parse_evidence(
            content_text=source.content_text,
            field=field,
            provider=_provider_for(theme),
        )
        if body.value is not None:  # admin override
            preview["value"] = body.value
            preview["confidence"] = "verified"
            preview["found"] = True
        if preview["value"] is None:
            log.warning("approve: no figure extracted", extra={"ticket_id": ticket_id, "field": field})
            raise HTTPException(422, "could not extract a figure; provide an explicit value")

        result = apply_lock(
            theme_id=ticket.theme_id,
            payload=payload,
            source_meta={
                "id": source.id,
                "type": source.type,
                "url": source.url,
                "publisher": source.publisher,
                "as_of_date": source.as_of_date,
                "confidence": source.confidence,
            },
            preview=preview,
        )
        ticket.status = "resolved"
        ticket.resolved_at = datetime.now(UTC)
        ticket.locked_value = preview["value"]
        source.verified = True
        log.info("ticket resolved + figure locked",
                 extra={"ticket_id": ticket_id, "value": preview["value"], **result})
        return {"status": "resolved", "ticket_id": ticket_id, **result}
