import os
from openai import OpenAI

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
    "NON_ACCADEMICO",
]

SYSTEM_PROMPT = (
    "Sei un assistente universitario. Analizzi titolo e descrizione di un evento "
    "del calendario di un docente e lo riconduci a una sola delle categorie del "
    "registro Esse3 che ti vengono fornite.\n"
    "Rispondi esclusivamente con una delle stringhe dell'elenco, senza "
    "punteggiatura aggiuntiva né spiegazioni.\n"
    "Se l'evento non è un'attività didattica o istituzionale (vita privata, "
    "ferie, visite personali), rispondi NON_ACCADEMICO."
)


def classify_activity(title: str, description: str = "") -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "NON_ACCADEMICO"

    client = OpenAI(api_key=api_key)

    elenco = "\n".join(f"- {c}" for c in ESSE3_CATEGORIES)
    user_prompt = (
        f"Categorie disponibili:\n{elenco}\n\n"
        f"Evento:\n- Titolo: {title}\n- Descrizione: {description}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=40,
        )
        categoria = response.choices[0].message.content.strip()
        return categoria if categoria in ESSE3_CATEGORIES else "NON_ACCADEMICO"
    except Exception as err:
        print(f"Errore durante la classificazione AI: {err}")
        return "NON_ACCADEMICO"