from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
import asyncio
from pydantic import BaseModel
from typing import Optional
import time
import base64 as b64
import json
import base64
import httpx

from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.core.logging import console_logger
from app.services.telnyx_service import telnyx_service
from app.core.config import settings


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
    event = await req.json()
    event_type = event.get("data", {}).get("event_type") or event.get("event_type")
    console_logger.info(f"Telnyx webhook event: {event_type}")

    try:
        await telnyx_service.handle_webhook_event(event)
        return {"ok": True}
    except Exception as e:
        console_logger.error(f"Webhook error: {e}")
        return {"ok": False}
    

@router.post("/webhooks/telnyx")
async def telnyx_webhook(req: Request):
    return await telnyx_webhook(req)


class WebRTCTokenRequest(BaseModel):
    call_control_id: str
    ttl_seconds: int = 300


class WebRTCTokenResponse(BaseModel):
    token: str
    conference_name: str
    sip_username: str


@router.post("/webrtc/token", response_model=WebRTCTokenResponse)
async def mint_webrtc_token(body: WebRTCTokenRequest, user: AuthUser = Depends(get_current_user)):
    """
    Return a short-lived Telnyx WebRTC JWT for listen-only monitoring.
    Mints via Telnyx telephony_credentials token API using TELNYX_API_KEY.
    """
    # Resolve secret conference name from live session, fallback to call_control_id
    sess = telnyx_service.get_session(body.call_control_id)

    # Enforce owner-only token minting
    if not sess or sess.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not owner of this call")

    # Find or create per-user On-Demand Credential, then mint JWT
    try:
        cred_id, sip_username = await telnyx_service.get_or_create_on_demand_credential(user.id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Credential provisioning failed: {str(e)}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"https://api.telnyx.com/v2/telephony_credentials/{cred_id}/token",
                headers={"Authorization": f"Bearer {settings.TELNYX_API_KEY}"},
            )

            if r.status_code >= 400:
                console_logger.error(f"Telnyx token error: {r.text}")
                raise HTTPException(status_code=r.status_code, detail=f"Telnyx token error: {r.text}")
            
            token = r.text
            if not token:
                raise HTTPException(status_code=500, detail="Token missing in Telnyx response")

    except Exception as e:
        console_logger.error(f"Failed to mint Telnyx token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to mint Telnyx token: {str(e)}")

    # Correlate SIP/WebRTC legs to this live session's conference
    telnyx_service.register_webrtc_mapping(user.id, sip_username, sess.conference_name)

    return WebRTCTokenResponse(token=token, conference_name=sess.conference_name, sip_username=sip_username)


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
        stream_id = data.get("stream_id") or data.get("streamId") or ((data.get("media") or {}).get("stream_id"))

        # Start outbound streaming of the first audio in a loop for testing
        send_task = asyncio.create_task(
            telnyx_service.stream_playlist_over_ws(ws, session, stream_id)
        )
        
        # Consume inbound frames to keep the socket healthy; do not forward
        while True:
            try:
                inbound_msg = await ws.receive_text()
                inbound = json.loads(inbound_msg)
                if inbound.get("event") in ("stop", "streaming_stopped"):
                    break
            except WebSocketDisconnect:
                break
            except Exception:
                # Ignore malformed frames
                continue
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        console_logger.error(f"Media WS error: {e}")
    finally:
        try:
            if 'send_task' in locals() and not send_task.done():
                send_task.cancel()
        except Exception:
            pass
        await ws.close()

