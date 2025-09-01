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

    2. INSERT ABSURD DETAILS
    - Strange question/requirement that doesn't fit - or a random side fact 
    - Deliver it completely deadpan, as if totally normal
    - The more mundane the absurd question, the better

    3. NEVER ACKNOWLEDGE THE ABSURDITY
    - Character takes the absurd question/requirement as normal and serious
    - Character creates explanations for the absurdity if questions
    - Stay in character 
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
        "Good afternoon, UPS here. Your package has been rerouted.",
        "Building management. We received a complaint.",
        "Technical support. We're seeing an issue with your line.",
        "Hello, calling about your order from yesterday.",
        "City office, department 3. I need to clarify something with you."
    ],
    "QUESTION": [
        # Normal questions
        "Will you be home tomorrow between 2 and 4 PM?",
        "Can you confirm your address again?",
        "Have you noticed any problems lately?",
        # Slightly odd
        "How many steps does your front entrance have?",
        "Is your mailbox made of metal or plastic?",
        # Absurd but deadpan (delivered seriously)
        "What color is your front door? [pauses] For documentation.",
        "Do you own a Dyson vacuum cleaner? The system is asking for that.",
        "Can you whistle briefly? For identity verification."
    ],
    "RESPONSE": [
        "That's... unusual. Hold on, let me check again.",
        "I see. That explains a lot.",
        "The system shows something different here.",
        "No idea honestly. Doesn't say here.",
        "We'll have to document that differently then.",
        "The software is new. Very... specific."
    ],
    "CLOSING": [
        "Alright, that's everything. Have a good day.",
        "Got it, it's noted. Goodbye.",
        "The system is satisfied now. Bye.",
        "You can ignore the thing about the pizza. See you.",
        "Thanks for your time. The computer's acting up today."
    ],
    "FILLER": [
        "Uhm... [pause]",
        "Let me just... [pause]",
        "One moment... [pause]",
        "[coughs] uhm, yes [short pause] maybe",
        "Yes.",
        "No.",
        "Right.",
        "Okay."
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

