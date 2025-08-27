from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import json

from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.core.logging import console_logger
from app.services.telnyx_service import telnyx_service


router = APIRouter(tags=["telnyx"])


class StartCallRequest(BaseModel):
    to_number: str
    scenario_id: int


class StartCallResponse(BaseModel):
    call_leg_id: str
    call_control_id: str
    call_session_id: str

@router.post("/call", response_model=StartCallResponse)
async def start_call(
    body: StartCallRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        call_leg_id, call_control_id, call_session_id = await telnyx_service.initiate_call(
            db_session=db,
            user_id=user.id,
            scenario_id=body.scenario_id,
            to_number=body.to_number,
        )
        return StartCallResponse(call_leg_id=call_leg_id, call_control_id=call_control_id, call_session_id=call_session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def telnyx_webhook(req: Request):
    # TODO: Add signature verification using TELNYX_WEBHOOK_SECRET
    event = await req.json()
    console_logger.info(f"Telnyx webhook event: {event}")
    try:
        await telnyx_service.handle_webhook_event(event)
        return {"ok": True}
    except Exception as e:
        console_logger.error(f"Webhook error: {e}")
        return {"ok": False}


@router.websocket("/media/{call_control_id}")
async def telnyx_media_ws(ws: WebSocket, call_control_id: str):
    await ws.accept()
    stream_id = None
    try:
        # Expect an initial message with stream metadata
        while stream_id is None:
            msg = await ws.receive_text()
            data = json.loads(msg)
            if isinstance(data, dict):
                stream_id = data.get("stream_id") or data.get("media", {}).get("stream_id")
                if data.get("event") in ("connected", "start") and not stream_id:
                    stream_id = data.get("stream_id")

        session = telnyx_service.get_session(call_control_id)
        if not session:
            await ws.close()
            return

        await telnyx_service.stream_playlist_over_ws(ws, session, stream_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        console_logger.error(f"WS error: {e}")
    finally:
        await ws.close()


