from typing import List, Dict, Any
from app.core.utils.enums import (
    ElevenLabsVoiceIdEnum,
    LanguageEnum,
    GenderEnum,
)


# Central curated voices catalog used by API and preview generation
# Each item: id, name, description, languages (order matters; first is primary), gender
VOICES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": ElevenLabsVoiceIdEnum.ENGLISH_MALE_JARNATHAN.value,
        "name": "Jarnathan",
        "description": "Well-rounded, young American voice",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.ENGLISH_FEMALE_CHELSEA.value,
        "name": "Chelsea",
        "description": "Pleasant, British, engaging",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.GERMAN_MALE_FELIX.value,
        "name": "Felix",
        "description": "Strong, documentary style",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
    },
    {
        "id": ElevenLabsVoiceIdEnum.GERMAN_FEMALE_SUSI.value,
        "name": "Susi",
        "description": "Soft, news presenter style",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
    },
]


def get_voices_catalog() -> List[Dict[str, Any]]:
    return VOICES_CATALOG


