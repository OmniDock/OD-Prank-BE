from deprecated import deprecated
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from pydantic import BaseModel

from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.core.logging import console_logger
from app.services.telnyx.handler import telnyx_handler


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
            user_id=str(user.id),
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
    

@deprecated(reason="This endpoint is deprecated we are not streaming media anymore. We do use Telnyx Playbacks.")
@router.websocket("/media/{call_control_id}")
async def telnyx_media_ws(ws: WebSocket, call_control_id: str):
    await telnyx_handler.handle_media_ws(ws, call_control_id)


# ################################################################################
# START CONTROL ENDPOINTS FOR ACTIVE CALLS
# ################################################################################


class PlayVoiceLineRequest(BaseModel):
    voice_line_id: int
    conference_name: str

class PlayVoiceLineResponse(BaseModel):
    success: bool
    message: str

@router.post("/call/play-voiceline")
async def play_voice_line(
    body: PlayVoiceLineRequest,
    user: AuthUser = Depends(get_current_user),
):
    try:
        console_logger.info(f"Playing voice line {body.voice_line_id} for user {user.id} in conference {body.conference_name}")
        await telnyx_handler.play_voice_line(user_id=str(user.id), conference_name=body.conference_name, voice_line_id=body.voice_line_id)
        return PlayVoiceLineResponse(success=True, message="Voice line streaming started")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

class StopVoiceLineRequest(BaseModel):
    conference_name: str
    voice_line_id: int

class StopVoiceLineResponse(BaseModel):
    success: bool
    message: str

@router.post("/call/stop-voiceline")
async def stop_voice_line(
    body: StopVoiceLineRequest,
    user: AuthUser = Depends(get_current_user),
):
    try:
        await telnyx_handler.stop_voice_line(user_id=str(user.id), conference_name=body.conference_name)
        return StopVoiceLineResponse(success=True, message="Voice line streaming stopped")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



class HangupCallRequest(BaseModel):
    conference_name: str

class HangupCallResponse(BaseModel):
    success: bool
    message: str

@router.post("/call/hangup")
async def hangup_call(
    body: HangupCallRequest,
    user: AuthUser = Depends(get_current_user),
):
    try:
        console_logger.info(f"Hanging up call for user {user.id} in conference {body.conference_name}")
        await telnyx_handler.hangup_call(user_id=str(user.id), conference_name=body.conference_name)
        return HangupCallResponse(success=True, message="Call terminated successfully")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
# ################################################################################
# END CONTROL ENDPOINTS FOR ACTIVE CALLS
# ################################################################################
