from sqlalchemy import select, func
from app.core.database import AsyncSession
from app.models.scenario import Scenario
from app.models.voice_line import VoiceLine
from app.models.voice_line_audio import VoiceLineAudio
from app.core.utils.enums import VoiceLineAudioStatusEnum
from app.core.auth import AuthUser

class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, user: AuthUser) -> dict:
        # Scenarios (aktiv)
        q_scenarios = select(func.count()).select_from(Scenario).where(
            Scenario.user_id == user.id, Scenario.is_active == True
        )
        # VoiceLines (via Scenario)
        q_voicelines = select(func.count()).select_from(VoiceLine).join(Scenario).where(
            Scenario.user_id == user.id
        )
        # TTS READY (via VoiceLine -> Scenario)
        q_tts_ready = (
            select(func.count())
            .select_from(VoiceLineAudio)
            .join(VoiceLine, VoiceLine.id == VoiceLineAudio.voice_line_id)
            .join(Scenario, Scenario.id == VoiceLine.scenario_id)
            .where(Scenario.user_id == user.id, VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY)
        )

        scenarios_total = (await self.db.execute(q_scenarios)).scalar() or 0
        voice_lines_total = (await self.db.execute(q_voicelines)).scalar() or 0
        tts_ready_total = (await self.db.execute(q_tts_ready)).scalar() or 0

        return {
            "scenarios_total": scenarios_total,
            "voice_lines_total": voice_lines_total,
            "tts_ready_total": tts_ready_total,
        }