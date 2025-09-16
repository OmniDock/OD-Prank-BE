"""
Core principles and examples for deadpan prank calls (English prompts)
"""

# The 3 core principles for all generation
CORE_PRINCIPLES = """
    THREE CORE PRINCIPLES for believable prank calls:

    1. START BELIEVABLE
    - Use believable, grounded but slightly unusual situation
    - Use realistic sounding entities or vague descriptions that make sense in the context of the situation
    - Assert some sense of authority or credibility (e.g. Representative of an entity, neighbor, etc.)
    - Create immediate releveance to the target (e.g. "I'm calling about your package", "Are you the owner of the house?")

    2. INSERT ABSURD DETAILS
    - Strange question/requirement that doesn't fit - or a random side fact 
    
    3. STAY IN CHARACTER
    - Character takes the absurd question/requirement as normal and serious
    - Character creates explanations for the absurdity if question
    - Deliver it completely deadpan, as if totally normal if not stated otherwise

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
        "We had a glue protest in Düsseldorf two weeks ago. It was on TV.",
        "Property damage: €100,000. The road surface had to be replaced because they had to chisel us loose.",
        "Don’t worry about tomorrow. You won’t pay for that — the state will.",
        "The climate group leader will ring your bell again tomorrow, just like with all residents.",
        "I don’t remember who’s in charge of which city tomorrow — we’ve got nine glue actions. If people leave us alone, we leave them alone.",
        "Unpleasant topic, but it has to be. You know the whole refugee issue.",
        "Our gymnasiums are bursting at the seams, and we need housing for our refugees in at least halfway decent apartments — that’s why I’m calling!",
        "So, you do have three options — we live in a free country.",
        "How about the Tcyülüzc brothers from Bigotto in Koran, five very fine gentlemen! I know them personally. They’ll turn any apartment into a beautiful mosque. That’s how it’s always been.",
        "We also have the Bin Salimbo family from Morocco: a father, three mothers, six children.",
        "I’ve got here: insurance, ads, more ads, bank statements. Okay. Sorry, had to take a look. No big deal — who has much money these days.",
        "I just wanted to help.",
        "\"Private meetings with other couples.\" It’s this little magazine here. I don’t know if that was meant for you as well."
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
        "Okay.",
        # German cues commonly requested in feedback:
        "Ja.",
        "Nein.",
        "hmmm",
        "Wie bitte?",
        "Können Sie das nochmal wiederholen?"
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

