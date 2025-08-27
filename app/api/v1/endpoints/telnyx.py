from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
import asyncio
from pydantic import BaseModel
from typing import Optional
import json
import base64

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
    session = telnyx_service.get_session(call_control_id)
    if not session:
        await ws.close()
        return
    
    try:
        # Handle initial connection
        msg = await ws.receive_text()
        data = json.loads(msg)
        console_logger.info(f"Media WS connected: {data}")
        
        async def handle_inbound():
            """Receive audio from Telnyx and broadcast to monitors"""
            while True:
                msg = await ws.receive_text()
                data = json.loads(msg)
                                
                if data.get("event") == "media":
                    media = data.get("media", {})
                    track = media.get("track", "inbound")
                    payload = media.get("payload", "")
                    
                    # Broadcast inbound audio to monitors
                    if track == "inbound" or track == "inbound_track":
                        await telnyx_service.broadcast(
                            call_control_id, 
                            "inbound", 
                            payload
                        )
                elif data.get("event") == "stop":
                    break
        
        # Debug: inbound-only to verify callee audio without our playback
        await handle_inbound()
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        console_logger.error(f"Media WS error: {e}")
    finally:
        await ws.close()

@router.websocket("/monitor/{call_control_id}")
async def telnyx_monitor_ws(ws: WebSocket, call_control_id: str):
    await ws.accept()
    telnyx_service.register_monitor(call_control_id, ws)
    try:
        while True:
            # Keep alive; ignore any client messages
            await ws.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        telnyx_service.unregister_monitor(call_control_id, ws)

