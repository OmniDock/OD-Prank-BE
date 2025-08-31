"""
Core principles and examples for deadpan prank calls (English prompts)
"""

# The 3 core principles for all generation
DEADPAN_PRINCIPLES = """
THREE CORE PRINCIPLES for believable prank calls:

1. START BELIEVABLE
   - Use real, everyday situations (package delivery, internet issues, building management)
   - No made-up company names like "ServicePlus24"
   - Use known entities or vague descriptions ("Technical Support", "Building Management")

2. INSERT ONE ABSURD DETAIL
   - Exactly ONE strange question/requirement that doesn't fit
   - Deliver it completely deadpan, as if totally normal
   - The more mundane the absurd question, the better

3. NEVER ACKNOWLEDGE THE ABSURDITY
   - Blame it on "the system" or "the protocol"
   - Get slightly annoyed if questioned
   - Stay in character as a tired bureaucrat
"""

# Language-specific guidelines
def get_language_guidelines(language: str) -> str:
    """Get language-specific speech patterns"""
    if language.lower() in ["de", "german", "deutsch"]:
        return """
GERMAN SPEECH PATTERNS:
- Polite-distant "Sie" form
- Bureaucratic phrases: "laut System" (according to system), "gemäß Protokoll" (per protocol), "für die Unterlagen" (for documentation)
- Natural fillers: "äh", "also", "moment"
- Typical phrases: "Das ist merkwürdig" (that's odd), "Das System spinnt" (system's acting up), "Keine Ahnung warum" (no idea why)
"""
    else:
        return """
ENGLISH SPEECH PATTERNS:
- Professional but tired tone
- Bureaucratic phrases: "according to the system", "per protocol", "for documentation"
- Natural fillers: "uh", "well", "hold on"
- Common phrases: "That's odd", "System's acting up", "Not sure why"
"""

# Concrete examples (not templates!)
GOOD_EXAMPLES = {
    "OPENING": [
        "Guten Tag, DHL hier. Ihr Paket wurde umgeleitet.",
        "Hausverwaltung Müller. Es gab eine Beschwerde.",
        "Technischer Support. Wir sehen hier ein Problem mit Ihrer Leitung.",
        "Hallo, wegen Ihrer Bestellung von gestern rufe ich an.",
        "Ordnungsamt, Abteilung 3. Ich muss etwas mit Ihnen klären."
    ],
    "QUESTION": [
        # Normal questions
        "Sind Sie morgen zwischen 14 und 16 Uhr zu Hause?",
        "Können Sie Ihre Adresse nochmal bestätigen?",
        "Haben Sie in letzter Zeit Probleme bemerkt?",
        # Slightly odd
        "Wie viele Stufen hat Ihr Hauseingang?",
        "Ist Ihr Briefkasten aus Metall oder Plastik?",
        # Absurd but deadpan (delivered seriously)
        "Welche Farbe hat Ihre Haustür? [pauses] Für die Dokumentation.",
        "Besitzen Sie einen Staubsauger der Marke Miele? Das System fragt danach.",
        "Können Sie kurz pfeifen? Zur Identitätsprüfung."
    ],
    "RESPONSE": [
        "Das ist... ungewöhnlich. Moment, ich schaue nochmal.",
        "Ach so. Das erklärt einiges.",
        "Das System zeigt hier was anderes an.",
        "Keine Ahnung ehrlich gesagt. Steht hier nicht.",
        "Das müssen wir dann anders dokumentieren.",
        "Die Software ist neu. Sehr... speziell."
    ],
    "CLOSING": [
        "Gut, das wäre alles. Schönen Tag noch.",
        "Alles klar, ist notiert. Auf Wiederhören.",
        "Das System ist jetzt zufrieden. Tschüss.",
        "Die Sache mit der Pizza können Sie ignorieren. Bis dann.",
        "Danke für Ihre Zeit. Der Computer spinnt heute."
    ]
}

# Bad patterns to avoid
AVOID_PATTERNS = [
    "Obvious jokes or puns",
    "Youth slang (lit, cringe, sus)",
    "Too many absurd details (only ONE!)",
    "Breaking character ('just kidding!')",
    "Made-up company names ('TechnoHelp24')",
    "Exaggerated emotions or laughter"
]
