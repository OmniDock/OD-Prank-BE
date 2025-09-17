from typing import Dict, Optional, Tuple

from app.core.config import settings
from app.core.logging import console_logger

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from deprecated import deprecated


class TelnyxHTTPClient: 

    def __init__(self):
        self.BASE_URL = "https://api.telnyx.com/v2"
        self.AUTH_HEADER = {"Authorization": f"Bearer {settings.TELNYX_API_KEY}"}
        self.WEBHOOK_URL = f"{settings.TELNYX_WEBHOOK_BASE_URL}{settings.API_V1_STR}/telnyx/webhook"
        self.FROM_NUMBER = settings.TELNYX_PHONE_NUMBER
        self.logging_enabled = True
        self.logger = console_logger
        self.TUNNEL_BASE_URL = settings.TUNNEL_URL.replace("https://", "wss://").replace("http://", "ws://")
        self._http = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self.AUTH_HEADER,
            timeout=httpx.Timeout(10.0, connect=4.0, read=10.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )

    def _headers(self, *, json_body: bool = False, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = dict(self.AUTH_HEADER)
        if json_body:
            headers["Content-Type"] = "application/json"
        if extra:
            headers.update(extra)
        return headers


    async def initiate_call(self, to_number: str) -> Tuple[str, str, str, str]:
        """
        Create an outbound call via Telnyx Call Control.
        Returns (call_leg_id, call_control_id, call_session_id, conference_name)
        """

        secret_conf = f"{secrets.token_urlsafe(64)}"

        payload = {
            "to": to_number,
            "from": self.FROM_NUMBER,
            "connection_id": settings.TELNYX_APPLICATION_ID,
            "webhook_url": self.WEBHOOK_URL,
            "conference_config": {
                "conference_name": secret_conf,
                "start_conference_on_enter": True,
                "end_conference_on_exit": True,
            }
        }

        console_logger.info(f"Initiating call to {to_number} with payload: {payload}")

        resp = await self._http.post(
            "/calls",
            headers=self._headers(json_body=True),
            json=payload,
            timeout=httpx.Timeout(20.0, connect=5.0, read=20.0),
        )
        resp.raise_for_status()
        data = resp.json()['data']


        call_leg_id = data["call_leg_id"]
        call_control_id = data.get("call_control_id")
        call_session_id = data.get("call_session_id")

        if self.logging_enabled:
            self.logger.info(f"Call Initiated: {data}")

        return call_leg_id, call_control_id, call_session_id, secret_conf
    

    async def answer_with_retry(self, ccid: str, retries: int = 4):
        ccid_path = quote(ccid, safe="")
        url = f"/calls/{ccid_path}/actions/answer"
        timeout = httpx.Timeout(10.0, connect=3.0, read=10.0)
        for attempt in range(1, retries+1):
            r = await self._http.post(
                url,
                headers=self._headers(json_body=True),
                timeout=timeout,
            )
            if r.status_code == 404 and attempt < retries:
                await asyncio.sleep(0.15 * attempt)  # 150ms, 300ms, ...
                continue
            r.raise_for_status()
            return


    async def join_conference_by_name(self, call_control_id: str, conference_name: str, retries: int = 5, mute: bool = False):
        conf_path = quote(conference_name, safe="")
        url = f"/conferences/{conf_path}/actions/join"
        body = {"call_control_id": call_control_id, "start_conference_on_enter": True, "mute": mute}
        timeout = httpx.Timeout(10.0, connect=3.0, read=10.0)
        for attempt in range(1, retries+1):
            r = await self._http.post(
                url,
                headers=self._headers(json_body=True),
                json=body,
                timeout=timeout,
            )
            if r.status_code in (404, 422) and attempt < retries:
                # 404: leg/conference not ready; 422: not answered yet -> give core a moment
                await asyncio.sleep(0.15 * attempt)
                continue
            r.raise_for_status()
            return
            

    async def get_or_create_on_demand_credential(self, user_id: str) -> str:
        """
        Find (by name) or create an On-Demand Telephony Credential under the configured SIP Connection.
        Returns the credential id to be used for JWT minting.
        # MAYBE JUST CREATING A NEW CREDENTIAL IS ENOUGH? 
        """

        unique_username = f"odprank-{user_id}"
        timeout = httpx.Timeout(15.0, connect=5.0, read=15.0)

        ### TRY TO FIND EXISTING CREDENTIAL BY NAME ###
        r = await self._http.get(
            "/telephony_credentials",
            headers=self._headers(),
            timeout=timeout,
        )

        if r.status_code >= 400:
            console_logger.error(f"list telephony_credentials error {r.status_code}: {r.text}")

        r.raise_for_status()
        items = (r.json() or {}).get("data") or []
        for item in items:
            expires_at = item.get("expires_at")
            if expires_at:
                tag_matches = item.get("tag") == unique_username
                # Fix: Use timezone-aware datetime for comparison
                expiry_matches = datetime.fromisoformat(item.get("expires_at")) > datetime.now(timezone.utc) + timedelta(minutes=5)
                if tag_matches and expiry_matches:
                    cid = item.get("id")
                    if cid:
                        return cid

        ### CREATE A NEW CREDENTIAL ###
        payload = {
            "connection_id": settings.TELNYX_CONNECTION_ID,
            "name": unique_username,
            "tag": unique_username,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()  # Also fix here for consistency
        }

        r2 = await self._http.post(
            "/telephony_credentials",
            headers=self._headers(json_body=True),
            json=payload,
            timeout=timeout,
        )
        if r2.status_code >= 400:
            console_logger.error(f"create telephony_credential error {r2.status_code}: {r2.text}")
        r2.raise_for_status()
        cid = ((r2.json() or {}).get("data") or {}).get("id")

        if not cid:
            raise RuntimeError("Created telephony credential but response missing id")

        return cid
        
    async def mint_webrtc_token(self, cred_id: str) -> str:
        r = await self._http.post(
            f"/telephony_credentials/{cred_id}/token",
            headers=self._headers(),
            timeout=httpx.Timeout(10.0, connect=3.0, read=10.0),
        )

        if r.status_code >= 400:
            console_logger.error(f"Telnyx token error: {r.text}")
            raise HTTPException(status_code=r.status_code, detail=f"Telnyx token error: {r.text}")

        token: Optional[str] = None
        content_type = (r.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            try:
                payload = r.json()
            except Exception:
                payload = None
            if isinstance(payload, dict):
                token = payload.get("token") or payload.get("data")
        if not token:
            token = r.text.strip()

        if not token:
            raise HTTPException(status_code=500, detail="Token missing in Telnyx response")
        return token 

    async def close(self) -> None:
        try:
            await self._http.aclose()
        except Exception as exc:
            self.logger.warning(f"Error closing Telnyx HTTP client: {exc}")

    async def hangup_call(self, call_control_id: str):
        """
        Hangup a call via Telnyx Call Control API.
        """
        ccid_path = quote(call_control_id, safe="")
        url = f"/calls/{ccid_path}/actions/hangup"

        resp = await self._http.post(
            url,
            headers=self._headers(json_body=True),
            json={},
            timeout=httpx.Timeout(10.0, connect=3.0, read=10.0),
        )

        if resp.status_code == 404:
            # Call might already be hung up
            self.logger.warning(f"Call {call_control_id} not found, may already be terminated")
            return

        if resp.status_code == 422:
            # Call might already be hung up
            self.logger.warning(f"Call {call_control_id} not found, may already be terminated")
            return

        resp.raise_for_status()

        if self.logging_enabled:
            self.logger.info(f"Call hung up: {call_control_id}") 

    async def playback_start(self, call_control_id: str, audio_url: str):
        """
        Start playback of an audio URL on a specific call leg.
        """
        ccid_path = quote(call_control_id, safe="")
        url = f"/calls/{ccid_path}/actions/playback_start"
        body = {"audio_url": audio_url}
        r = await self._http.post(
            url,
            headers=self._headers(json_body=True),
            json=body,
            timeout=httpx.Timeout(15.0, connect=3.0, read=15.0),
        )
        if r.status_code >= 400:
            self.logger.error(f"playback_start error {r.status_code}: {r.text}")
        r.raise_for_status()

    async def playback_stop(self, call_control_id: str):
        """
        Stop playback on a specific call leg.
        """
        ccid_path = quote(call_control_id, safe="")
        url = f"/calls/{ccid_path}/actions/playback_stop"
        r = await self._http.post(
            url,
            headers=self._headers(json_body=True),
            json={},
            timeout=httpx.Timeout(10.0, connect=3.0, read=10.0),
        )
        if r.status_code >= 400:
            self.logger.error(f"playback_stop error {r.status_code}: {r.text}")
        r.raise_for_status()

    async def conference_play(self, conference_name: str, audio_url: str, *, call_control_ids: list[str] | None = None):
        """
        Play an audio URL to all participants in a conference (or targeted legs).
        """
        conf_path = quote(conference_name, safe="")
        url = f"/conferences/{conf_path}/actions/play"
        body = {"audio_url": audio_url}
        if call_control_ids:
            body["call_control_ids"] = call_control_ids
        r = await self._http.post(
            url,
            headers=self._headers(json_body=True),
            json=body,
            timeout=httpx.Timeout(15.0, connect=3.0, read=15.0),
        )
        if r.status_code >= 400:
            self.logger.error(f"conference play error {r.status_code}: {r.text}")
        r.raise_for_status()


    async def conference_stop(self, conference_name: str, call_control_ids: list[str] | None = None):
        """
        Stop any audio being played on the conference (optionally target legs).
        """
        conf_path = quote(conference_name, safe="")
        url = f"/conferences/{conf_path}/actions/stop"
        body = {}
        if call_control_ids:
            body["call_control_ids"] = call_control_ids
        r = await self._http.post(
            url,
            headers=self._headers(json_body=True),
            json=body,
            timeout=httpx.Timeout(10.0, connect=3.0, read=10.0),
        )
        if r.status_code >= 400:
            self.logger.error(f"conference stop error {r.status_code}: {r.text}")
        r.raise_for_status()

  


    #@deprecated(reason="This method is deprecated we are not streaming media anymore. We do use Telnyx Playbacks.")
    def _get_media_stream_url(self, call_control_id: str) -> str:
        return f"{self.TUNNEL_BASE_URL}{settings.API_V1_STR}/telnyx/media/{call_control_id}"

    #@deprecated(reason="This method is deprecated we are not streaming media anymore. We do use Telnyx Playbacks.")
    async def start_media_stream(self, call_control_id: str):
        """ 
        Telling Telnyx to start a media stream over the WebSocket.
        That way we can stream audio into different legs of the call. 
        """
        stream_url = self._get_media_stream_url(call_control_id)
        body = {
            "stream_url": stream_url,
            "stream_track": "both_tracks",
            "stream_codec": "PCMU",
            "stream_bidirectional_mode": "rtp",
        }

        resp = await self._http.post(
            f"/calls/{call_control_id}/actions/streaming_start",
            headers=self._headers(json_body=True),
            json=body,
            timeout=httpx.Timeout(20.0, connect=5.0, read=20.0),
        )
        if resp.status_code >= 400:
            self.logger.error(f"Telnyx streaming_start error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
