# Request/Response Models
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.core.utils.enums import LanguageEnum, GenderEnum, ElevenLabsModelEnum

class SingleTTSRequest(BaseModel):
    voice_line_id: int
    voice_id: Optional[str] = None
    model: Optional[ElevenLabsModelEnum] = ElevenLabsModelEnum.ELEVEN_TTV_V3

class BatchTTSRequest(BaseModel):
    voice_line_ids: List[int] = Field(..., min_items=1, max_items=50)  # Limit batch size
    voice_id: Optional[str] = None
    model: Optional[ElevenLabsModelEnum] = ElevenLabsModelEnum.ELEVEN_TTV_V3

class ScenarioTTSRequest(BaseModel):
    scenario_id: int
    voice_id: Optional[str] = None
    model: Optional[ElevenLabsModelEnum] = ElevenLabsModelEnum.ELEVEN_TTV_V3

class RegenerateTTSRequest(BaseModel):
    voice_line_id: int
    voice_id: Optional[str] = None
    model: Optional[ElevenLabsModelEnum] = ElevenLabsModelEnum.ELEVEN_TTV_V3

class TTSResult(BaseModel):
    voice_line_id: int
    success: bool
    signed_url: Optional[str] = None
    storage_path: Optional[str] = None
    error_message: Optional[str] = None

class TTSResponse(BaseModel):
    success: bool
    total_processed: int
    successful_count: int
    failed_count: int
    results: List[TTSResult]

class VoiceItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    languages: List[LanguageEnum]
    gender: GenderEnum
    preview_url: Optional[str] = None
    avatar_url: Optional[str] = None

class VoiceListResponse(BaseModel):
    voices: List[VoiceItem]
    
class PublicTTSTestRequest(BaseModel):
    text: str
    voice_id: str
    model: Optional[ElevenLabsModelEnum] = ElevenLabsModelEnum.ELEVEN_TTV_V3
    voice_settings: Optional[Dict[str, Any]] = None

class PublicTTSTestResponse(BaseModel):
    success: bool
    storage_path: Optional[str] = None
    public_url: Optional[str] = None
    error_message: Optional[str] = None