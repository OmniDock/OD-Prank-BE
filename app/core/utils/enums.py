import enum

class LanguageEnum(enum.Enum):
    ENGLISH = "ENGLISH"
    GERMAN = "GERMAN"


class VoiceLineTypeEnum(enum.Enum):
    OPENING = "OPENING"
    QUESTION = "QUESTION"
    RESPONSE = "RESPONSE"
    CLOSING = "CLOSING"
