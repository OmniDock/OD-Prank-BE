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
    {
        "id": ElevenLabsVoiceIdEnum.SIMON.value,
        "name": "Simon",
        "description": "Young german voice with a warm, realtable tone and a naturally slow pace",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.THOMAS.value,
        "name": "Thomas",
        "description": "Conversational German male voice.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.BASTI.value,
        "name": "Basti",
        "description": "Authentic modern voice from Germany",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.YVONNE.value,
        "name": "Yvonne",
        "description": "German Female voice. Great for casual conversations.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.RAMONA.value,
        "name": "Ramona",
        "description": "Voice that creates calmness, while keeping the audience hooked.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.DANA.value,
        "name": "Dana",
        "description": "Middle aged German female with deep, warm, nasal voice.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.ANNY.value,
        "name": "Anny",
        "description": "Natural, soft female voice for storytelling",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.ROBERT.value,
        "name": "Robert",
        "description": "Young aussie voice perfect for conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.MAHESH.value,
        "name": "Mahesh",
        "description": "Young Indian voice to engage, assist and connect in natural conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.MIKE.value,
        "name": "Mike",
        "description": "Old american voice. Great for conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.LUKE.value,
        "name": "Luke",
        "description": "Italian man speaking english with an italian accent.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.BLONDIE.value,
        "name": "Blondie",
        "description": "British woman with a warm, natural voice.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.EMILY.value,
        "name": "Emily",
        "description": "A soft soothing voice that radiates warmth and kindness.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.IVANNA.value,
        "name": "Ivanna",
        "description": "A natural conversational American female voice with a youthful tone",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.LEONI.value,
        "name": "Leoni",
        "description": "International Cosmopolitan and educated voice",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
    }
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