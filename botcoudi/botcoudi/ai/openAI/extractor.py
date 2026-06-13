import json
import logging
import os

import openai
from django.conf import settings


logger = logging.getLogger(__name__)


def extraer_datos_via_openai(
    historial_texto,
    api_key,
    idioma='es',
    model=None,
    raise_on_error=False,
    timeout_seconds=None,
    max_retries=None,
    system_prompt_override=None
):
    if timeout_seconds is None:
        timeout_seconds = os.getenv("OPENAI_TIMEOUT", "5")
    if max_retries is None:
        max_retries = os.getenv("OPENAI_MAX_RETRIES", "2")

    timeout_seconds = float(timeout_seconds)
    max_retries = int(max_retries)

    client = openai.OpenAI(
        api_key=api_key,
        timeout=timeout_seconds,
        max_retries=max_retries,
    )

    model = (
        model
        or getattr(settings, "OPENAI_MODEL", None)
        or os.getenv("OPENAI_MODEL")
    )

    # PROMPTS POR IDIOMA
    prompts = {
        'es': {
            'sistema': (
                "Eres un analizador de conversaciones. Del historial que te proporcionaré:\n"
                "1. SOLO extrae información de los mensajes marcados como 'Usuario:', IGNORA completamente los mensajes de 'Bot:'\n"
                "2. Si el usuario proporciona múltiples valores para el mismo campo (ej: dos números de teléfono), "
                "usa el ÚLTIMO que proporcionó o el que parezca correcto según el contexto (ej: si corrige un error)\n"
                "3. Identifica correcciones explícitas como 'perdón, es 555...' o 'me equivoqué, es...'\n"
                "4. Devuelve un JSON con: nombre, correo, celular (null si no existe)\n\n"
                "5. Separa el nombre, celular y correo del usuario.\n"
                "IMPORTANTE: Los mensajes del Bot pueden contener números o emails de ejemplo - IGNÓRALOS COMPLETAMENTE.\n"
                "Solo usa información que el Usuario haya escrito.\n\n"
                "Ejemplo:\n"
                "Usuario: Hola\n"
                "Bot: Hola, mi teléfono es 1234567890\n"
                "Usuario: Mi nombre es Juan\n"
                "Usuario: Mi cel es 5551234567\n"
                "Usuario: Perdón, es 5559876543\n"
                "Ejemplo de salida:\n"
                "{ \"nombre\": \"Juan Pérez\", \"correo\": \"juan@mail.com\", \"celular\": \"55123456789\"}\n"
            ),
            'user_prompt': "Analiza esta conversación y extrae SOLO los datos del Usuario:\n\n{historial_procesado}"
        },
        'en': {
            'sistema': (
                "You are a conversation analyzer. From the history I will provide you:\n"
                "1. ONLY extract information from messages marked as 'Usuario:', COMPLETELY IGNORE 'Bot:' messages\n"
                "2. If the user provides multiple values for the same field (e.g.: two phone numbers), "
                "use the LAST one they provided or the one that seems correct according to context (e.g.: if they correct an error)\n"
                "3. Identify explicit corrections like 'sorry, it's 555...' or 'I made a mistake, it's...'\n"
                "4. Return a JSON with: nombre, correo, celular (null if it doesn't exist)\n\n"
                "5. Separate the user's name, phone, and email.\n"
                "IMPORTANT: Bot messages may contain example numbers or emails - IGNORE THEM COMPLETELY.\n"
                "Only use information that the User has written.\n\n"
                "Example:\n"
                "Usuario: Hello\n"
                "Bot: Hello, my phone is 1234567890\n"
                "Usuario: My name is John\n"
                "Usuario: My phone is 5551234567\n"
                "Usuario: Sorry, it's 5559876543\n"
                "Example output:\n"
                "{ \"nombre\": \"John Smith\", \"correo\": \"john@mail.com\", \"celular\": \"55123456789\"}\n"
            ),
            'user_prompt': "Analyze this conversation and extract ONLY the User's data:\n\n{historial_procesado}"
        }
    }

    # Usar prompt según idioma
    prompt_config = prompts.get(idioma, prompts['es'])

    # Procesar el historial para marcar claramente usuario vs bot
    historial_procesado = historial_texto.replace("user:", "Usuario:").replace("bot:", "Bot:")
    final_system_prompt = system_prompt_override or prompt_config['sistema']

    messages = [
        {"role": "system", "content": final_system_prompt},
        {"role": "user", "content": prompt_config['user_prompt'].format(historial_procesado=historial_procesado)}
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=200
        )
    except Exception as error:
        logger.warning("OpenAI extractor error: %s", error)
        if raise_on_error:
            raise
        return {}

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        if raise_on_error:
            raise
        return {}
