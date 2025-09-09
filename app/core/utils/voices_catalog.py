from typing import List, Dict, Any
from app.core.utils.enums import (
    ElevenLabsVoiceIdEnum,
    LanguageEnum,
    GenderEnum,
)


# ################################################################################
# Central curated voices catalog used by API and preview generation
# ################################################################################

PREVIEW_VERSION = "v9"
VOICES_CATALOG: List[Dict[str, Any]] = [
    # {
    #     "id": ElevenLabsVoiceIdEnum.SUSI.value,
    #     "name": "Susi",
    #     "description": "Soft, news presenter style",
    #     "languages": [LanguageEnum.GERMAN],
    #     "gender": GenderEnum.FEMALE,
    # },
    {
        "id": ElevenLabsVoiceIdEnum.MARTIN.value,
        "name": "Martin",
        "description": "Sympathische, bodenständige Stimme mit einem Hauch von Abenteuerlust.",
        "avatar_url": "martin.webp",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "intro": "[exhales] Hey, ich bin Martin. [curious] Ich geb’s zu: Eigentlich bin ich der Vernünftige hier… aber heute mach ich mal ’ne Ausnahme. [laughs] Also, lass uns was Verrücktes starten – ich bin dabei, wenn du’s bist.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.TIMO.value,
        "name": "Timo",
        "description": "Locker, spontan und immer für einen Spaß zu haben.",
        "avatar_url": "timo.webp",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "intro": "[exhales] Servus, ich bin Timo. [curious] Normalerweise halte ich mich aus so was raus… aber heute hab ich richtig Lust auf Quatsch. [laughs] Also, komm – wir machen das Beste draus. [whispers] Aber pssst… nicht verraten.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.SIMON.value,
        "name": "Simon",
        "description": "Young german voice with a warm, realtable tone and a naturally slow pace",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "avatar_url": "simon.webp",
        "intro": "[exhales] Hey! Ich bin Simon – und ja, ich weiß, meine Stimme klingt vielleicht ein bisschen zu nett für das hier.[curious] Aber genau deshalb wird’s witzig. [laughs] Versprochen.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.THOMAS.value,
        "name": "Thomas",
        "description": "Conversational German male voice.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "avatar_url": "thomas.webp",
        "intro": "[sighs] Hey, ich bin Thomas. [curious] Und bevor du fragst: Nein, ich hab keine Ahnung, worauf du dich hier eingelassen hast.[laughs] Aber genau das macht’s ja spannend, oder? [whispers] Nur du, ich… und ein bisschen Chaos.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.BASTI.value,
        "name": "Basti",
        "description": "Authentic modern voice from Germany",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.MALE,
        "avatar_url": "basti.webp",
        "intro": "Jo, ich bin Basti. [laughs] Kein Plan, wie ich hier gelandet bin – aber jetzt bin ich da.[curious]Und wenn du dachtest, das hier wird normal… [whispers] nope.[excited] Also lehn dich zurück und genieß die Show.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.YVONNE.value,
        "name": "Yvonne",
        "description": "German Female voice. Great for casual conversations.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "yvonne.webp",
        "intro": "Hey du, ich bin Yvonne. [curious] Keine Sorge, ich beiß nicht – zumindest meistens nicht [laughs]. [exhales]Ich bin hier für den Spaß… und vielleicht ein kleines bisschen Chaos.[whispers] Aber pssst, nicht weitersagen. Also… bereit?",
    },
    {
        "id": ElevenLabsVoiceIdEnum.RAMONA.value,
        "name": "Ramona",
        "description": "Voice that creates calmness, while keeping the audience hooked.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "ramona.webp",
        "intro": "[exhales] Hallo. Ich bin Ramona. [curious] Ich weiß… das hier fühlt sich gerade ein bisschen zu ruhig an für das, was gleich passiert. [laughs] Aber keine Sorge – ich hab alles unter Kontrolle. [whispers] Atme einmal tief durch… denn gleich wird’s wild.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.DANA.value,
        "name": "Dana",
        "description": "Middle aged German female with deep, warm, nasal voice.",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "dana.webp",
        "intro": "Hallo, ich bin Dana. [curious] Und ja… ich hab diese Stimme, bei der man nie so ganz weiß, ob man gleich lacht oder gegrillt wird [laughs]. [whispers] Ich sag nur: Gut festhalten. Denn jetzt wird’s interessant.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.ANNY.value,
        "name": "Anny",
        "description": "Natural, soft female voice for storytelling",
        "languages": [LanguageEnum.GERMAN],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "anny.webp",
        "intro": "Hey, ich bin Anny. [curious] Stell dir einfach vor, ich erzähl dir ’ne kleine Geschichte… [laughs] …nur dass sie völlig aus dem Ruder läuft. [whispers] Aber genau das macht’s spannend, oder?",
    },
    {
        "id": ElevenLabsVoiceIdEnum.ROBERT.value,
        "name": "Robert",
        "description": "Young aussie voice perfect for conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
        "avatar_url": "robert.webp",
        "intro": "Hey mate, I’m Robert – all the way from Australia. I know [laughs], the accent gives it away[laughs]. But don’t worry, I’m not here to wrestle a kangaroo [laughs]. [whispers] Just here to mess with people a little. [slight accent] You in?",
    },
    {
        "id": ElevenLabsVoiceIdEnum.MAHESH.value,
        "name": "Mahesh",
        "description": "Young Indian voice to engage, assist and connect in natural conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
        "avatar_url": "mahesh.webp",
        "intro": "[exhales] Hi, I’m Mahesh – your friendly voice from India. [curious] I’m here to help... or maybe just stir up a little fun. [laughs] Depends on how you look at it. Ready for something unexpected?",
    },
    {
        "id": ElevenLabsVoiceIdEnum.MIKE.value,
        "name": "Mike",
        "description": "Old american voice. Great for conversations.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
        "avatar_url": "mike2.webp",
        "intro": "Hey there, name’s Mike. [curious] Been around long enough to know when something’s about to go sideways. [laughs] And trust me… this one’s heading there fast. [whispers] You sure you’re ready for this?",
    },
    {
        "id": ElevenLabsVoiceIdEnum.LUKE.value,
        "name": "Luke",
        "description": "Italian man speaking english with an italian accent.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.MALE,
        "avatar_url": "luke.webp",
        "intro": "[very excited] Ciao, I’m Luke – yes, from Italy. [strong accent] You can probably hear it already. [curious] They told me this was just a little joke... [laughs] but I think we might take it a bit too far.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.BLONDIE.value,
        "name": "Blondie",
        "description": "British woman with a warm, natural voice.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "blondie.webp",
        "intro": "[exhales] Hey love, I’m Blondie – and yes, the name fits. [laughs] But don’t let that fool you. [curious] I know exactly what I’m doing… most of the time. [whispers] Just play along and smile.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.EMILY.value,
        "name": "Emily",
        "description": "A soft soothing voice that radiates warmth and kindness.",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "emily.webp",
        "intro": "Hi there, I’m Emily. [curious] I know… I sound way too gentle for whatever THIS is. [laughs] But don’t worry – I promise to be nice. Mostly. [whispers] Just breathe… and trust me. You’re in good hands.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.IVANNA.value,
        "name": "Ivanna",
        "description": "A natural conversational American female voice with a youthful tone",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "ivanna.webp",
        "intro": "[exhales] Hey! I’m Ivanna. [curious] I sound pretty chill, right? [laughs] Yeah… that’s usually how it starts [whispers] Just act normal and maybe no one gets pranked. [laughs] Kidding.",
    },
    {
        "id": ElevenLabsVoiceIdEnum.LEONI.value,
        "name": "Leoni",
        "description": "International Cosmopolitan and educated voice",
        "languages": [LanguageEnum.ENGLISH],
        "gender": GenderEnum.FEMALE,
        "avatar_url": "leoni.webp",
        "intro": "Hello, I’m Leoni. [curious] I usually keep things elegant and under control… [laughs] But today, we’re making a little exception. [whispers] Just between us – it’s more fun that way. [excited] Shall we?",
    }
]

DEFAULT_SETTINGS = {
    "stability": 0.0,
    "use_speaker_boost": False,
    "similarity_boost": 1.3,
    "style": 1.8,
    "speed": 1.2,
}

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