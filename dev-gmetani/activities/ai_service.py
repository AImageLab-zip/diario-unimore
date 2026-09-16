import os
from google import genai

ESSE3_CATEGORIES = [
    "assistenza laureandi",
    "attività did. atenei convenzionati",
    "attività didattiche integrative",
    "attività dottorati di ricerca",
    "attività master",
    "Attività PNRR (solo RTD-A)",
    "attività scuole di specializzazione",
    "compiti organizzativi interni",
    "esami di laurea",
    "esami di profitto",
    "orient. e tutor. piani di studio, stages",
    "preparazione lezioni",
    "ricevimento studenti",
    "NON_ACCADEMICO"  # Per eventi personali come palestra, visite mediche, pranzi
]

def classify_activity(title: str, description: str = "") -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "NON_ACCADEMICO"

    client = genai.Client(api_key=api_key)

    prompt = f"""
Sei un assistente universitario. Il tuo compito è analizzare il titolo e la descrizione di un evento da Google Calendar di un professore e ricondurlo ESATTAMENTE a una delle seguenti categorie del registro Esse3:

{chr(10).join(f'- {cat}' for cat in ESSE3_CATEGORIES)}

Regole:
1. Rispondi ESCLUSIVAMENTE con una delle stringhe dell'elenco sopra, senza punteggiatura aggiuntiva né spiegazioni.
2. Se l'evento non è un'attività didattica/istituzionale universitaria (es. vita privata, ferie, visite personali), rispondi con: NON_ACCADEMICO.

Evento:
- Titolo: {title}
- Descrizione: {description}
"""

    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        category = response.text.strip()
        if category in ESSE3_CATEGORIES:
            return category
        return "NON_ACCADEMICO"
    except Exception as err:
        print(f"Errore durante la classificazione AI: {err}")
        return "NON_ACCADEMICO"