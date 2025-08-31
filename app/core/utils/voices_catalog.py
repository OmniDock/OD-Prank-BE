from typing import List, Dict, Any
from app.core.utils.enums import (
    ElevenLabsVoiceIdEnum,
    LanguageEnum,
    GenderEnum,
)


# ################################################################################
# Central curated voices catalog used by API and preview generation
# ################################################################################

PREVIEW_VERSION = "v8"
VOICES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": ElevenLabsVoiceIdEnum.SUSI.value,
        "name": "Susi",
        "description": "Soft, news presenter style",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.MARTIN.value,
        "name": "Martin",
        "description": "-",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.TIMO.value,
        "name": "Timo",
        "description": "-",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
    },
]


def get_voices_catalog() -> List[Dict[str, Any]]:
    return VOICES_CATALOG


def get_voice_id(language: LanguageEnum, gender: GenderEnum) -> str:
    """Get the default voice ID for a language and gender combination"""
    voice_map = {
        (LanguageEnum.ENGLISH, GenderEnum.MALE): ElevenLabsVoiceIdEnum.MARTIN.value, # TODO: FIND PROPER ENGLISH MALE VOICE
        (LanguageEnum.ENGLISH, GenderEnum.FEMALE): ElevenLabsVoiceIdEnum.SUSI.value, # TODO: FIND PROPER ENGLISH FEMALE VOICE
        (LanguageEnum.GERMAN, GenderEnum.MALE): ElevenLabsVoiceIdEnum.MARTIN.value,
        (LanguageEnum.GERMAN, GenderEnum.FEMALE): ElevenLabsVoiceIdEnum.SUSI.value,
    }
    
    return voice_map.get((language, gender), ElevenLabsVoiceIdEnum.MARTIN.value)