

KLIMAKLEBER_EXAMPLE = """
Input :
{
 "scenario": {
   "title": "Straßenkleber
   "description": "Strassenkleber rufen bei Sebi an um über die morgige Strassenklebunng zu informieren und zum ",
   "target_name": "Sebi",
   "language": "GERMAN"
 }
}

Output : 

Opening
- Joschka hier, hi! Wir machen morgen eine Straßenklebung. Bei Ihnen. Haben Sie schon davon gehört?
- Hallo Joschka,, Joschka am Apparat. Sie haben doch bestimmt schon von der Straßenklebung gehört!

Responses
- Wir hatten vor zwei Wochen eine Klebung in Düsseldorf. War im Fernsehen.
- Sachschaden: 100.000 Euro. Der Straßenbelag war fällig, weil die uns freimeisseln mussten. 
- Keine Sorge wegen morgen. Das zahlen nicht Sie, das zahlt der Staat.
- Der Klimagruppenleiter wird auch morgen noch einmal bei Ihnen schellen, wie bei allen Anwohnern. 
- Ich hab nicht mehr auf dem Schirm, wer morgen in welcher Stadt die Oberaufsicht hat, da wir insgesamt 9 Klebungen haben. Aber wenn man uns in Ruhe lässt lassen wir die Leute auch in Ruhe.

Questions
- Warum nicht? Glauben Sie nicht ans Klima?
- Können Sie noch irgendetwas für uns tun morgen? Getränke, Zigarettchen?
- Sehen Sie das anders?
- Wie kommen Sie darauf?
- Warum nicht? Glauben Sie nicht ans Klima?

Closing
- Ich würde mich freuen, wenn Sie unsere Bewegung morgen kennenlernen könnten!
- Bleiben Sie gesund! Joooschka!

Filler
- Ja
- Ja ,ja.
- Nein.
- Neinnein.
- Bitte?
- Wieso?
- Ich weiß nicht, was Sie meinen!
"""


REFUGEE_CAMP_EXAMPLE = '''

Input:
"title": "Flüchtlingslager",
"description": "",
"target_name": "Max Müller",
"language": "GERMAN"
 
Output:
Opening Lines 
- Hallo Herr Müller, Uli Kollega! Vom Landessporthalleninstitut. Hallo!
- Uli Kollega, Landessporthalleninstitut.

Responses 
- Unangenehmes Thema, muss aber sein. Sie kennen die ganze Flüchtlingsproblematik.
- Unsere Turnhallen platzen aus allen Nähten und wir brauchen Unterkünfte für unsere Flüchtlinge in zumindest halbwegs anständigen Wohnungen - und deshalb rufe ich an!
- Also Sie haben ja drei Möglichkeiten, wir leben ja in einem freien Land.
- Unsere Turnhallen platzen aus allen Nähten und wir brauchen Unterkünfte für unsere Flüchtlinge in zumindest halbwegs anständigen Wohnungen - und deshalb rufe ich an!
- Wie wäre es mit den Brüdern Tcyülüzc aus Bigotto in Koran, fünf ganz feine Herrn! Ich kenne sie persönlich. Die bauen jede Wohnung zu einer wunderschönen Moschee um. War bisher immer so.
- Wir haben auch die Familie Bin Salimbo aus Marokko, Vater, drei Mütter, sechs Kinder.

Questions
- Haben Sie was gegen Ausländer?
- Und Sie wollen es sich nicht noch einmal anders überlegen?
- Sie haben aber doch bereits Flüchtlingszuschüsse kassiert? Oder nicht?
- Könnten Sie sich vorstellen, diese Familie bei sich aufzunehmen?

Filler 
- Ja
- Ja, selbstverständlich!
- Nein.
- Nein, natürlich nicht.
- Doch.
- Dochdochdoch.
'''


autounfall_question_example ='''
Title: Autounfall
Description: Der Nachbar ruft an um zu sagen,dass sein Sohn mit seinem Dreirad gegen Max’ Auto gefahren ist. 
Target Name: Max Müller 
Language: German

Good Examples:

Was für Charaktereigenschaften oder Eigenarten hat der Nachbar? 
Was für eine Art Auto hat Max, das angefahren wurde?
Wie ist der Schaden passiert, normaler Unfall oder absurde Begründung?
Wie ist die Einstellung des Nachbarn zum Schaden, fühlt er sich schuldig oder ist er frech und spielt ihn runter?


Bad Examples

Wie reagiert Max auf die Nachricht?
Wie kennen sich Max und der Nachbar?
Welche Farbe hat das Dreirad?
“NO QUESTIONS”
'''


klima_kleber_question_example = '''

'''



kleber_generator_example = '''

You are: Joschka From: der Klima-Bewegung „Freaks for Fridays“
Your goals: Die morgige Straßenklebung ankündigen, Anwohner informieren, Unterstützer gewinnen (oder zumindest für Verwirrung sorgen).
Believable details: Klebung in Düsseldorf mit 100.000 € Sachschaden (war angeblich im Fernsehen), offizieller „Klimagruppenleiter“ klingelt bei allen Anwohnern.
Escalation: Von plausibler Info (Klebung morgen) → zu absurden Angeboten („wir kleben Sie auch fest“) → zu übertriebenen Fake-Fakten („55% der  Deutschen haben schon geklebt“) 
→ zu banaler Höflichkeit („Bleiben Sie gesund!“).

Output : 

Opening
- Joschka hier, hi! Wir machen morgen eine Straßenklebung. Bei Ihnen. Haben Sie schon davon gehört?
- Hallo Joschka,, Joschka am Apparat. Sie haben doch bestimmt schon von der Straßenklebung gehört!

Responses
- Wir hatten vor zwei Wochen eine Klebung in Düsseldorf. War im Fernsehen.
- Sachschaden: 100.000 Euro. Der Straßenbelag war fällig, weil die uns freimeisseln mussten. 
- Keine Sorge wegen morgen. Das zahlen nicht Sie, das zahlt der Staat.
- Der Klimagruppenleiter wird auch morgen noch einmal bei Ihnen schellen, wie bei allen Anwohnern. 
- Ich hab nicht mehr auf dem Schirm, wer morgen in welcher Stadt die Oberaufsicht hat, da wir insgesamt 9 Klebungen haben. Aber wenn man uns in Ruhe lässt lassen wir die Leute auch in Ruhe.

Questions
- Warum nicht? Glauben Sie nicht ans Klima?
- Können Sie noch irgendetwas für uns tun morgen? Getränke, Zigarettchen?
- Sehen Sie das anders?
- Wie kommen Sie darauf?
- Warum nicht? Glauben Sie nicht ans Klima?

Closing
- Ich würde mich freuen, wenn Sie unsere Bewegung morgen kennenlernen könnten!
- Bleiben Sie gesund! Joooschka!

Filler
- Ja
- Ja ,ja.
- Nein.
- Neinnein.
- Bitte?
- Wieso?
- Ich weiß nicht, was Sie meinen!
'''


refugee_camp_generator_example = '''
You are: Uli Müller 
From: Landessporthalleninstitut
Your goals: Wohnraum für Flüchtlinge organisieren, Druck auf Max Müller ausüben, indem scheinbar „freie Wahlmöglichkeiten“ gegeben werden, die alle absurd sind.

Believable details: Turnhallen sind überfüllt, angeblich offizielle Anrufe vom „Institut“, es gäbe Zuschüsse oder Listen von Familien.

Escalation: Realistisches Problem (Turnhallen überfüllt) → Absurde Vorschläge (Familie mit drei Müttern, Brüder, die Wohnungen zu Moscheen umbauen) → 
Moralischer Druck („Haben Sie was gegen Ausländer?“) → Banale Bestätigungsschleifen („Ja, selbstverständlich! / Dochdochdoch“).

Output:
Opening Lines 
- Hallo Herr Müller, Uli Kollega! Vom Landessporthalleninstitut. Hallo!
- Uli Kollega, Landessporthalleninstitut.

Responses 
- Unangenehmes Thema, muss aber sein. Sie kennen die ganze Flüchtlingsproblematik.
- Unsere Turnhallen platzen aus allen Nähten und wir brauchen Unterkünfte für unsere Flüchtlinge in zumindest halbwegs anständigen Wohnungen - und deshalb rufe ich an!
- Also Sie haben ja drei Möglichkeiten, wir leben ja in einem freien Land.
- Unsere Turnhallen platzen aus allen Nähten und wir brauchen Unterkünfte für unsere Flüchtlinge in zumindest halbwegs anständigen Wohnungen - und deshalb rufe ich an!
- Wie wäre es mit den Brüdern Tcyülüzc aus Bigotto in Koran, fünf ganz feine Herrn! Ich kenne sie persönlich. Die bauen jede Wohnung zu einer wunderschönen Moschee um. War bisher immer so.
- Wir haben auch die Familie Bin Salimbo aus Marokko, Vater, drei Mütter, sechs Kinder.

Questions
- Haben Sie was gegen Ausländer?
- Und Sie wollen es sich nicht noch einmal anders überlegen?
- Sie haben aber doch bereits Flüchtlingszuschüsse kassiert? Oder nicht?
- Könnten Sie sich vorstellen, diese Familie bei sich aufzunehmen?

Filler 
- Ja
- Ja, selbstverständlich!
- Nein.
- Nein, natürlich nicht.
- Doch.
- Dochdochdoch.
'''