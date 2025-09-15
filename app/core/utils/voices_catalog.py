from typing import List, Dict, Any, Optional
from app.core.utils.enums import (
    ElevenLabsVoiceIdEnum,
    LanguageEnum,
    GenderEnum,
)


# ################################################################################
# Central curated voices catalog used by API and preview generation
# ################################################################################

PREVIEW_VERSION = "v10"

DEFAULT_SETTINGS = {
    "stability": 0.0,
    "use_speaker_boost": False,
    "similarity_boost": 0.5,
    "style": 1.6,
    "speed": 2.0,
}

DEFAULT_SETTINGS_V2 = {
    "stability": 0.5,
    "use_speaker_boost": False,
    "similarity_boost": 0.7,
    "style": 1.1,
    "speed": 0.95
}



VOICES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": ElevenLabsVoiceIdEnum.MARTIN.value,
        "name": "Martin",
        "description": "Older, serious sounding german voice with slight austrian accent",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "intro": "[serious][mock-official] Servus Martin mein Name, ... [pause][smirks in voice]zuständig fürs gemeinsame Blödsinn machen.",
        "avatar_url": "martin.webp",
        "voice_settings": DEFAULT_SETTINGS,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.TIMO.value,
        "name": "Timo",
        "description": "Locker, spontan und immer für einen Spaß zu haben.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "intro": "[chill] Was geht? Timo hier! [quicker] Lass dich von der gechillten Stimme nicht täuschen... [slightly excited] wir nehmen heute ein paar Leute richtig hops, hast' Bock?",
        "avatar_url": "timo.webp",
        "voice_settings": DEFAULT_SETTINGS,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.THOMAS.value,
        "name": "Thomas",
        "description": "Conversational German male voice.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "avatar_url": "thomas.webp",
        "intro": "[sighs] Hey, ich bin Thomas. [curious] Und bevor du fragst: Nein, ich hab keine Ahnung, worauf du dich hier eingelassen hast.[laughs] Aber genau das macht’s ja spannend, oder? [whispers] Nur du, ich… und ein bisschen Chaos.",
        "voice_settings": DEFAULT_SETTINGS,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.DANA.value,
        "name": "Dana",
        "description": "Middle aged German female with deep, warm, nasal voice.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "dana.webp",
        "intro": "Hallo, ich bin Dana. [curious] Und ja… ich hab diese Stimme, bei der man nie so ganz weiß, ob man gleich lacht oder gegrillt wird [laughs]. [whispers] Ich sag nur: Gut festhalten. Denn jetzt wird’s interessant.",
        "voice_settings": DEFAULT_SETTINGS,
        "tts_speedup": 1.15,
    
    },
    {
        "id": ElevenLabsVoiceIdEnum.ANNY.value,
        "name": "Anny",
        "description": "Natural, soft female voice for storytelling",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "anny.webp",
        "intro": "Hey, ich bin Anny. [curious] Stell dir einfach vor, ich erzähl dir ’ne kleine Geschichte… [laughs] …nur dass sie völlig aus dem Ruder läuft. [whispers] Aber genau das macht’s spannend, oder?",
        "voice_settings": DEFAULT_SETTINGS,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.ROBERT.value,
        "name": "Robert",
        "description": "Young aussie voice perfect for conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
        "avatar_url": "robert.webp",
        "intro": "Hey mate, I’m Robert – all the way from Australia. I know [laughs], the accent gives it away[laughs]. But don’t worry, I’m not here to wrestle a kangaroo [laughs]. [whispers] Just here to mess with people a little. [slight accent] You in?",
        "voice_settings": DEFAULT_SETTINGS_V2,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.MAHESH.value,
        "name": "Mahesh",
        "description": "Young Indian voice to engage, assist and connect in natural conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
        "avatar_url": "mahesh.webp",
        "intro": "[exhales] Hi, I’m Mahesh – your friendly voice from India. [curious] I’m here to help... or maybe just stir up a little fun. [laughs] Depends on how you look at it. Ready for something unexpected?",
        "voice_settings": DEFAULT_SETTINGS,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.MIKE.value,
        "name": "Mike",
        "description": "Old american voice. Great for conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
        "avatar_url": "mike2.webp",
        "intro": "Hey there, name’s Mike. [curious] Been around long enough to know when something’s about to go sideways. [laughs] And trust me… this one’s heading there fast. [whispers] You sure you’re ready for this?",
        "voice_settings": DEFAULT_SETTINGS,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.BLONDIE.value,
        "name": "Blondie",
        "description": "British woman with a warm, natural voice.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "blondie.webp",
        "intro": "[exhales] Hey love, I’m Blondie – and yes, the name fits. [laughs] But don’t let that fool you. [curious] I know exactly what I’m doing… most of the time. [whispers] Just play along and smile.",
        "voice_settings": DEFAULT_SETTINGS_V2,
        "tts_speedup": 1.15,
    },
    {
        "id": ElevenLabsVoiceIdEnum.EMILY.value,
        "name": "Emily",
        "description": "A soft soothing voice that radiates warmth and kindness.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "emily.webp",
        "intro": "Hi there, I’m Emily. [curious] I know… I sound way too gentle for whatever THIS is. [laughs] But don’t worry – I promise to be nice. Mostly. [whispers] Just breathe… and trust me. You’re in good hands.",
        "voice_settings": DEFAULT_SETTINGS_V2,
        "tts_speedup": 1.15,
    }
]



def get_voices_catalog() -> List[Dict[str, Any]]:
    return VOICES_CATALOG

def get_voice_settings_for(voice_id: Optional[str]) -> Dict[str, Any]:
    if not voice_id:
        return DEFAULT_SETTINGS
    item = next((v for v in VOICES_CATALOG if v.get("id") == voice_id), None)
    return (item or {}).get("voice_settings") or DEFAULT_SETTINGS

def get_voice_id(language: LanguageEnum, gender: GenderEnum) -> str:
    """Get the default voice ID for a language and gender combination"""
    voice_map = {
        (LanguageEnum.ENGLISH, GenderEnum.MALE): ElevenLabsVoiceIdEnum.MARTIN.value, # TODO: FIND PROPER ENGLISH MALE VOICE
        (LanguageEnum.ENGLISH, GenderEnum.FEMALE): ElevenLabsVoiceIdEnum.SUSI.value, # TODO: FIND PROPER ENGLISH FEMALE VOICE
        (LanguageEnum.GERMAN, GenderEnum.MALE): ElevenLabsVoiceIdEnum.MARTIN.value,
        (LanguageEnum.GERMAN, GenderEnum.FEMALE): ElevenLabsVoiceIdEnum.SUSI.value,
    }
    
    return voice_map.get((language, gender), ElevenLabsVoiceIdEnum.MARTIN.value)