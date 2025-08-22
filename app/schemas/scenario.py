from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from app.core.utils.enums import LanguageEnum, VoiceLineTypeEnum

class ScenarioCreateRequest(BaseModel):
    """Schema for creating a new scenario"""
    title: str = Field(..., min_length=1, max_length=255, description="Scenario title")
    target_name: str = Field(..., min_length=1, max_length=255, description="Target name")
    description: str = Field(..., max_length=5096, description="Scenario description")
    language: LanguageEnum = Field(default=LanguageEnum.GERMAN, description="Scenario language")
    
    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty or just whitespace')
        return v.strip()
    
    @field_validator('description')
    @classmethod
    def description_optional_cleanup(cls, v):
        if v is not None:
            v = v.strip()
            return v if v else None
        return v

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "title": "Pizza Delivery Prank",
                "description": "A funny prank call pretending to be a pizza delivery service",
                "language": "en",
                "target_name": "John Doe"
            }
        }


class VoiceLineResponse(BaseModel):
    """Schema for voice line response"""
    id: int
    text: str
    type: VoiceLineTypeEnum
    order_index: int
    storage_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        use_enum_values = True


class ScenarioResponse(BaseModel):
    """Schema for scenario response"""
    id: int
    title: str
    description: Optional[str] = None
    language: LanguageEnum
    preferred_voice_id: Optional[str] = None
    target_name: str
    is_safe: bool
    is_not_safe_reason: Optional[str] = None
    is_public: bool
    is_active: bool
    voice_lines: List[VoiceLineResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        use_enum_values = True


class ScenarioCreateResponse(BaseModel):
    """Schema for scenario creation response"""
    scenario: ScenarioResponse
    processing_summary: dict  # Summary of the LangChain processing results
    
    class Config:
        from_attributes = True



class VoiceLineEnhancementRequest(BaseModel):
    """Schema for voice line enhancement request"""
    voice_line_ids: List[int] = Field(..., min_items=1, max_items=50, description="List of voice line IDs to enhance")
    user_feedback: str = Field(..., min_length=1, max_length=2000, description="User feedback for enhancement")
    
    class Config:
        json_schema_extra = {
            "example": {
                "voice_line_ids": [1, 2, 3],
                "user_feedback": "Make them funnier and add more pauses"
            }
        }


class VoiceLineEnhancementResult(BaseModel):
    """Schema for individual voice line enhancement result"""
    voice_line_id: int
    original_text: str
    enhanced_text: Optional[str] = None
    error: Optional[str] = None
    safety_passed: bool
    safety_issues: List[str] = []


class VoiceLineEnhancementResponse(BaseModel):
    """Schema for voice line enhancement response"""
    success: bool
    total_processed: int
    successful_count: int
    failed_count: int
    successful_enhancements: List[VoiceLineEnhancementResult] = []
    failed_enhancements: List[VoiceLineEnhancementResult] = []
    user_feedback: str