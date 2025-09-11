from enum import Enum   

class LanguageEnum(Enum):
    ENGLISH = "ENGLISH"
    GERMAN = "GERMAN"

class VoiceLineTypeEnum(Enum):
    OPENING = "OPENING"
    QUESTION = "QUESTION"
    RESPONSE = "RESPONSE"
    CLOSING = "CLOSING"
    FILLER = "FILLER"

class VoiceLineAudioStatusEnum(Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"



#########################################
# ElevenLabs Voice IDs and Metadata
#########################################
class GenderEnum(Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

class ElevenLabsVoiceIdEnum(Enum):
    """Top-tier ElevenLabs voice IDs for different languages and genders"""
    SUSI = "v3V1d2rk6528UrLKRuy8" 
    MARTIN = "a5qh6GnXXXlZQrD05l99"
    TIMO = "LiBuTwmXQ5kpwE9fvUP3"
    SIMON = "K5ZVtkkBnuPY6YqXs70E"
    THOMAS = "lUbNEaW6UqGepBMr82aV"
    BASTI = "Rc6mVxOkevStnSH2pUO9"
    YVONNE = "fBs1tCpaSMsPcbMkLQlk"
    RAMONA = "yUy9CCX9brt8aPVvIWy3"
    DANA = "otF9rqKzRHFgfwf6serQ"
    ANNY = "ZgahlWh5FVSG7MFjZwPE"
    ROBERT = "W7iMfDi1kcxkyeiQDrg4"
    MAHESH = "iLrek0aeAREetkK9NhwJ"
    MIKE = "WF4i4ZlVIKR1m1lLbJji"
    LUKE = "KlyEVp7Cr4uWil0rM5Lq"
    BLONDIE = "exsUS4vynmxd379XN4yO"
    EMILY = "c51VqUTljshmftbhJEGm"
    IVANNA = "4NejU5DwQjevnR6mh3mb"
    LEONI = "pBZVCk298iJlHAcHQwLr"

class ElevenLabsModelEnum(Enum):
    """ElevenLabs model options"""
    ELEVEN_TTV_V3 = "eleven_v3"      


class ProductNameEnum(Enum):
    SINGLE = "single"
    WEEKLY = "weekly"
    MONTHLY = "monthly"