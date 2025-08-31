import enum

class LanguageEnum(enum.Enum):
    ENGLISH = "ENGLISH"
    GERMAN = "GERMAN"

class VoiceLineTypeEnum(enum.Enum):
    OPENING = "OPENING"
    QUESTION = "QUESTION"
    RESPONSE = "RESPONSE"
    CLOSING = "CLOSING"
    FILLER = "FILLER"

class VoiceLineAudioStatusEnum(enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"



#########################################
# ElevenLabs Voice IDs and Metadata
#########################################
class GenderEnum(enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

class ElevenLabsVoiceIdEnum(enum.Enum):
    """Top-tier ElevenLabs voice IDs for different languages and genders"""
    SUSI = "v3V1d2rk6528UrLKRuy8" 
    MARTIN = "a5qh6GnXXXlZQrD05l99"
    TIMO = "LiBuTwmXQ5kpwE9fvUP3"

class ElevenLabsModelEnum(enum.Enum):
    """ElevenLabs model options"""
    ELEVEN_TTV_V3 = "eleven_v3"      


