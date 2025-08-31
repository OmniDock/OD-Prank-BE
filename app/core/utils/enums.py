import enum

class LanguageEnum(enum.Enum):
    ENGLISH = "ENGLISH"
    GERMAN = "GERMAN"


class VoiceLineTypeEnum(enum.Enum):
    OPENING = "OPENING"
    QUESTION = "QUESTION"
    RESPONSE = "RESPONSE"
    CLOSING = "CLOSING"





### ElevenLabs Voice IDs

class GenderEnum(enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class ElevenLabsVoiceIdEnum(enum.Enum):
    """Top-tier ElevenLabs voice IDs for different languages and genders"""
    
    # English Voices
    ENGLISH_MALE_JARNATHAN = "c6SfcYrb2t09NHXiT80T"     # Well-rounded, young American voice
    ENGLISH_FEMALE_CHELSEA = "NHRgOEwqx5WZNClv5sat"  # Pleasant, British, engaging
    ENGLISH_MALE_YASH = "sXXU5CoXEMsIqocfPUh2"
    # German Voices (using multilingual voices optimized for German)
    GERMAN_MALE_FELIX = "pqHfZKP75CvOlQylNhV4"        # Strong, documentary style
    GERMAN_FEMALE_SUSI = "v3V1d2rk6528UrLKRuy8"     # Soft, news presenter style

    GERMAN_MALE_SIMON = "K5ZVtkkBnuPY6YqXs70E"
    GERMAN_FEMALE_LAURA = "zKHQdbB8oaQ7roNTiDTK"

    MALE_MARK = "UgBBYS2sOqTuMpoF3BR0"


    # SEBASTIANS NEW FAVORITE
    MARTIN_R_PRO = "a5qh6GnXXXlZQrD05l99"
    TIMO = "LiBuTwmXQ5kpwE9fvUP3"


class ElevenLabsModelEnum(enum.Enum):
    """ElevenLabs model options"""
    MULTILINGUAL_V2 = "eleven_multilingual_v2"        # Good quality, 29 languages  
    TURBO_V2_5 = "eleven_turbo_v2_5"                  # Fast generation, good quality
    FLASH_V2_5 = "eleven_flash_v2_5"                  # Ultra-low latency, 32 languages
    ELEVEN_TTV_V3 = "eleven_v3"            # Ultra-low latency, 32 languages


# Voice line audio asset status
class VoiceLineAudioStatusEnum(enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


# Helper function to get voice ID based on language and gender
def get_voice_id(language: LanguageEnum, gender: GenderEnum) -> str:
    """Get the default voice ID for a language and gender combination"""
    voice_map = {
        (LanguageEnum.ENGLISH, GenderEnum.MALE): ElevenLabsVoiceIdEnum.ENGLISH_MALE_JARNATHAN.value,
        (LanguageEnum.ENGLISH, GenderEnum.FEMALE): ElevenLabsVoiceIdEnum.ENGLISH_FEMALE_CHELSEA.value,
        (LanguageEnum.GERMAN, GenderEnum.MALE): ElevenLabsVoiceIdEnum.GERMAN_MALE_FELIX.value,
        (LanguageEnum.GERMAN, GenderEnum.FEMALE): ElevenLabsVoiceIdEnum.GERMAN_FEMALE_SUSI.value,
    }
    
    return voice_map.get((language, gender), ElevenLabsVoiceIdEnum.GERMAN_MALE_FELIX.value)