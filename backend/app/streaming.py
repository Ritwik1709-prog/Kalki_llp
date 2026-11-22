import asyncio
from contextlib import suppress
from io import BytesIO
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas


async def heartbeat_stream(events, interval=15):
    iterator = events.__aiter__()
    pending = asyncio.create_task(anext(iterator))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield ": keep-alive\n\n"
                continue
            try:
                value = pending.result()
            except StopAsyncIteration:
                break
            yield value
            pending = asyncio.create_task(anext(iterator))
    finally:
        pending.cancel()
        with suppress(asyncio.CancelledError, StopAsyncIteration):
            await pending
        if hasattr(iterator, "aclose"):
            await iterator.aclose()


def sse_response(events):
    return StreamingResponse(heartbeat_stream(events), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


def pdf_response(lines):
    """Internal renderer; callers must authorize exact-version Partner approval."""
    buffer = BytesIO()
    document = canvas.Canvas(buffer)
    document.setTitle("Kalki LLP — Confidential Audit Dossier")
    document.setAuthor("Kalki LLP")

    def page_branding():
        document.setFont("Helvetica-Bold", 10)
        document.drawString(40, 810, "KALKI LLP • CONFIDENTIAL AUDIT DOSSIER")
        document.setFont("Helvetica", 8)
        document.drawString(40, 25, "KALKI LLP • CONFIDENTIAL AUDIT DOSSIER")
        document.drawRightString(555, 25, f"Page {document.getPageNumber()}")
        document.setFont("Helvetica", 11)

    page_branding()
    y = 780
    for line in lines:
        for start in range(0, max(1, len(line)), 90):
            document.drawString(40, y, line[start:start+90])
            y -= 16
            if y < 55:
                document.showPage()
                page_branding()
                y = 780
    document.save()
    buffer.seek(0)

    def chunks():
        try:
            while chunk := buffer.read(65536):
                yield chunk
        finally:
            buffer.close()
    return StreamingResponse(chunks(), media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="kalki-dossier.pdf"'})
