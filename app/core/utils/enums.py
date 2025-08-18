import enum

class LanguageEnum(enum.Enum):
    ENGLISH = "en"
    GERMAN = "de"


class VoiceLineTypeEnum(enum.Enum):
    OPENING = "opening"
    QUESTION = "question"
    RESPONSE = "response"
    CLOSING = "closing"
