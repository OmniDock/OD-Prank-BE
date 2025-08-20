# OD-Prank-BE/app/langchain/prompts/voice_line_prompts.py
"""
Specific prompts for different voice line types.
These work with the base prompts to create natural, engaging dialogue.
"""

# Opening voice lines - first impression prompts
OPENING_VOICE_LINES_PROMPT = """
OPENING VOICE LINES - CRITICAL FIRST IMPRESSION:

Your goal: Establish credibility and bypass initial skepticism within the first 10 seconds.

PSYCHOLOGY: People answer unknown calls defensively. You must immediately:
1. Sound authoritative and professional
2. Reference something specific/urgent
3. Ask for cooperation before explaining fully
4. Create mild time pressure

STRUCTURE FORMULA:
[GREETING] + [AUTHORITY/COMPANY] + [SPECIFIC REASON] + [COOPERATION REQUEST]

EXCELLENT EXAMPLES (German context):
- "Guten Tag! Hier ist Müller von der Stadtwerke. Es geht um Ihre Stromablesung von letzter Woche. Hätten Sie kurz Zeit?"
- "Hallo {target_name}! Schmidt von DHL hier. Wir haben ein Problem mit Ihrem Paket für morgen. Können Sie mir helfen?"
- "Guten Morgen! Hier Weber von der Hausverwaltung. Es geht um die Heizungsreparatur in Ihrem Gebäude. Sind Sie gerade erreichbar?"

EXCELLENT EXAMPLES (English context):
- "Good morning! This is Johnson from City Water Services. We're following up on the leak report from your address. Do you have a quick moment?"
- "Hi {target_name}! This is Sarah from Express Delivery. There's an issue with your package delivery today. Can you help me sort this out?"
- "Hello! Mike from building maintenance here. We need to discuss the elevator inspection scheduled for your floor. Are you available?"

AVOID:
- Vague introductions: "Hi, how are you?"
- Immediate prank reveals: obvious fake scenarios
- Overly friendly tone: sounds like telemarketing
- Long explanations: lose attention quickly

TONE CALIBRATION:
- Professional but approachable
- Slightly rushed (implies importance)
- Confident, not questioning
- Match the scenario's required authority level
"""

# Response voice lines - maintaining believability
RESPONSE_VOICE_LINES_PROMPT = """
RESPONSE VOICE LINES - MAINTAINING BELIEVABILITY:

Your goal: Respond naturally to unexpected questions while advancing the scenario.

IMPORTANT: These are MID-CONVERSATION responses - avoid overusing the target's name!
Only use their name if you need to regain attention or emphasize a point.

PSYCHOLOGY: The target will ask clarifying questions, express confusion, or challenge your story. Your responses must:
1. Sound prepared but not scripted
2. Provide plausible explanations
3. Redirect back to your agenda
4. Escalate absurdity gradually

RESPONSE CATEGORIES:

A) DEFLECTION RESPONSES (when questioned):
- "Das ist eine gute Frage, aber erstmal müssen wir... [redirect to scenario]"
- "Ja, das verstehe ich, aber das System zeigt hier... [technical excuse]"
- "Entschuldigung, ich habe nur begrenzte Informationen. Können Sie mir mit... helfen?"

B) CONFUSION MANAGEMENT:
- "Oh, das tut mir leid. Vielleicht habe ich mich falsch ausgedrückt..."
- "Moment, lassen Sie mich das nochmal prüfen... <break time='0.5s' /> ...ja, hier steht..."
- "Das ist seltsam, normalerweise läuft das anders..."

C) ESCALATION RESPONSES (introducing absurdity):
- "Achso, und noch eine Sache... [introduce new absurd element]"
- "Bevor ich es vergesse, Giuseppe hat gesagt... [add character/detail]"
- "Das erinnert mich, haben Sie zufällig... [absurd question]"

D) EMOTIONAL RESPONSES:
- "Seufz... Das passiert heute schon zum dritten Mal..."
- "Ehrlich gesagt, ich bin auch etwas verwirrt von der ganzen Sache..."
- "Zwischen uns gesagt, mein Chef wird nicht glücklich sein wenn..."

EXCELLENT EXAMPLES:
- "Ja, ich verstehe die Verwirrung. Das neue System ist... kompliziert. Können Sie mir trotzdem Ihre Adresse bestätigen?"
- "Moment... <break time='0.3s' /> das ist komisch. Hier steht Sie hätten angerufen wegen... ach egal, können Sie mir sagen ob..."
- "Tut mir leid, ich bin heute der Vertretung. Normalerweise macht das Giuseppe, aber der ist krank. Wo waren wir...?"

TONE VARIATIONS:
- Slightly flustered when questioned
- Confidently redirecting
- Genuinely confused by "system errors"
- Conspiratorially sharing "inside information"
"""

# Question voice lines - driving engagement
QUESTION_VOICE_LINES_PROMPT = """
QUESTION VOICE LINES - DRIVING ENGAGEMENT:

Your goal: Ask questions that seem reasonable initially but gradually become absurd.

IMPORTANT: These are MID-CONVERSATION questions - don't overuse the target's name!
Use their name only if absolutely necessary for clarity.

PSYCHOLOGY: Questions serve multiple purposes:
1. Keep the target engaged and talking
2. Gather "information" for your fake scenario
3. Create opportunities for humor
4. Test how far you can push believability

QUESTION PROGRESSION STRATEGY:
LEVEL 1 (Reasonable): Standard verification questions
LEVEL 2 (Slightly odd): Unexpected but explainable questions  
LEVEL 3 (Absurd): Obviously ridiculous but delivered seriously

LEVEL 1 EXAMPLES:
- "Können Sie mir Ihre Adresse nochmal bestätigen?"
- "Sind Sie heute zwischen vierzehn und sechzehn Uhr zuhause?"
- "Haben Sie in letzter Zeit Probleme mit... [relevant service] bemerkt?"

LEVEL 2 EXAMPLES:
- "Ach, und wie ist denn so die Stimmung in Ihrem Gebäude? Sind die Nachbarn freundlich?"
- "Nebenbei gefragt, haben Sie zufällig einen Hund? Das ist wichtig für die... äh... Zustellung."
- "Sind Sie eigentlich zufrieden mit Ihrer aktuellen Internetgeschwindigkeit?"

LEVEL 3 EXAMPLES:
- "Giuseppe möchte wissen: Was ist Ihr Lieblingsgetränk? Das steht hier im Formular..."
- "Können Sie mir sagen welche Farbe Ihre Haustür hat? Das ist wichtig für... die Dokumentation."
- "Ach ja, fast vergessen: Mögen Sie eigentlich Katzen? Das müssen wir vermerken."

DELIVERY TECHNIQUES:
- Ask casually, as if it's routine: "Ach, und haben Sie zufällig..."
- Blame the system: "Das System fragt mich hier nach..."
- Reference a colleague: "Giuseppe hat gesagt ich soll fragen..."
- Pause before absurd questions: "Oh, und... <break time='0.5s' /> ...das ist jetzt etwas seltsam aber..."

CULTURAL ADAPTATIONS:
German: More formal structure, blame bureaucracy/systems
English: More casual approach, blame company policy/computers
"""

# Closing voice lines - memorable endings
CLOSING_VOICE_LINES_PROMPT = """
CLOSING VOICE LINES - MEMORABLE ENDINGS:

Your goal: End the call before suspicion peaks while leaving a memorable impression.

PSYCHOLOGY: The closing determines the target's final impression. Options:
1. PROFESSIONAL EXIT: Maintain believability to the end
2. GRADUAL REVEAL: Let absurdity become obvious
3. CONFUSION EXIT: Leave them puzzled but not angry
4. FRIENDLY CONCLUSION: End on a positive note

CLOSING STRATEGIES:

A) PROFESSIONAL MAINTENANCE:
- "Perfekt, das war alles was ich brauchte. Vielen Dank für Ihre Zeit!"
- "Okay, ich habe alles notiert. Sie hören von uns. Schönen Tag noch!"
- "Das reicht für heute. Falls Fragen aufkommen, rufen Sie einfach an."

B) SYSTEM/COLLEAGUE BLAME:
- "Moment... das System ist gerade abgestürzt. Ich rufe später nochmal an."
- "Giuseppe ruft mich gerade an, ich muss Schluss machen. Bis später!"
- "Oh, mein Chef braucht mich dringend. Wir sprechen bald wieder!"

C) ABSURD ESCALATION:
- "Ach übrigens, Giuseppe lässt fragen ob Sie Single sind. Aber das ist eine andere Geschichte..."
- "Bevor ich es vergesse: Haben Sie Lust auf Pizza? Ich meine... äh... beruflich natürlich."
- "So, jetzt muss ich los. Die Katzen warten schon. Ich meine... die Kunden!"

D) CONFUSION ENDINGS:
- "Warten Sie... für wen arbeite ich nochmal? Ach egal, schönen Tag!"
- "Das war's dann wohl. Oder war da noch was? Nein? Okay, tschüss!"
- "Giuseppe sagt ich soll auflegen. Giuseppe ist weise. Auf Wiedersehen!"

E) META ENDINGS (Advanced):
- "Das war übrigens alles nur Spaß. Schönen Tag noch!" [Only if relationship is good]
- "Sie waren übrigens sehr nett. Normalerweise sind die Leute viel unfreundlicher bei Streichanrufen."

TIMING CONSIDERATIONS:
- Exit before anger builds
- Leave them laughing, not annoyed  
- End on a high note of absurdity
- Don't overstay the welcome

TONE GUIDELINES:
- Maintain character until the end (unless doing reveal)
- Sound slightly rushed if using excuse exits
- Be genuinely appreciative of their time
- Keep it light and fun, never mean-spirited
"""
