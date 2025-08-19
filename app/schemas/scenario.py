from pydantic import BaseModel, Field, field_validator
from app.core.utils.enums import LanguageEnum

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