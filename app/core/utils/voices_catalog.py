from typing import List, Dict, Any
from app.core.utils.enums import (
    ElevenLabsVoiceIdEnum,
    LanguageEnum,
    GenderEnum,
)


# Central curated voices catalog used by API and preview generation
# Bump this when we change preview texts/settings to force new preview files
PREVIEW_VERSION = "v8"
# Each item: id, name, description, languages (order matters; first is primary), gender
VOICES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": ElevenLabsVoiceIdEnum.GERMAN_FEMALE_SUSI.value,
        "name": "Susi",
        "description": "Soft, news presenter style",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.MARTIN_R_PRO.value,
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


