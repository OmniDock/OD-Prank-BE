from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.core.logging import console_logger
from app.services.telnyx.handler import telnyx_handler
from app.core.config import settings


router = APIRouter(tags=["telnyx"])


class StartCallRequest(BaseModel):
    to_number: str
    scenario_id: int

class StartCallResponse(BaseModel):
    call_leg_id: str
    call_control_id: str
    call_session_id: str
    conference_name: str
    webrtc_token: str

class WebRTCTokenRequest(BaseModel):
    call_control_id: str

class WebRTCTokenResponse(BaseModel):
    token: str
    conference_name: str

@router.post("/call", response_model=StartCallResponse)
async def start_call(
    body: StartCallRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:

        # Also mint WebRTC token immediately so frontend can join
        token = await telnyx_handler.get_webrtc_token(user.id)

        call_leg_id, call_control_id, call_session_id, conference_name = await telnyx_handler.initiate_call(
            db_session=db,
            user_id=user.id,
            scenario_id=body.scenario_id,
            to_number=body.to_number,
        )

        return StartCallResponse(
            call_leg_id=call_leg_id,
            call_control_id=call_control_id,
            call_session_id=call_session_id,
            conference_name=conference_name,
            webrtc_token=token,
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def telnyx_webhook(req: Request):
    try:
        event = await req.json()
        await telnyx_handler.handle_webhook_event(event)
        return {"ok": True}
    except Exception as e:
        console_logger.error(f"Webhook error: {e}")
        return {"ok": False}
    

@router.websocket("/media/{call_control_id}")
async def telnyx_media_ws(ws: WebSocket, call_control_id: str):
    await telnyx_handler.handle_media_ws(ws, call_control_id)


@router.post("/webrtc/token", response_model=WebRTCTokenResponse)
async def mint_webrtc_token(body: WebRTCTokenRequest, user: AuthUser = Depends(get_current_user)):
    """
    Return a short-lived Telnyx WebRTC JWT for listen-only monitoring.
    Mints via Telnyx telephony_credentials token API using TELNYX_API_KEY.
    """

    sess = telnyx_handler._session_service.get_session(body.call_control_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden: not owner of this call")

    token = await telnyx_handler.get_webrtc_token(user.id)
    return WebRTCTokenResponse(token=token, conference_name=sess.conference_name)



