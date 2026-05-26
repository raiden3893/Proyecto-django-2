import json
import logging
import os

import anthropic
from django.conf import settings


logger = logging.getLogger(__name__)


def extraer_datos_via_claude(
    historial_texto,
    api_key,
    idioma='es',
    model=None,
    raise_on_error=False,
    timeout_seconds=None,
    max_retries=None,
):
    if timeout_seconds is None:
        timeout_seconds = os.getenv("CLAUDE_TIMEOUT", "5")
    if max_retries is None:
        max_retries = os.getenv("CLAUDE_MAX_RETRIES", "2")

    timeout_seconds = float(timeout_seconds)
    max_retries = int(max_retries)

    client = anthropic.Anthropic(
        api_key=api_key,
        timeout=timeout_seconds,
        max_retries=max_retries,
    )

    historial_procesado = historial_texto.replace("user:", "Usuario:").replace("bot:", "Bot:")

    model = (
        model
        or getattr(settings, "CLAUDE_MODEL", None)
        or os.getenv("CLAUDE_MODEL")
        or os.getenv("ANTHROPIC_MODEL")
    )

    try:
        message = client.messages.create(
            model=model,
            max_tokens=1200,
            system="Eres un analizador de conversaciones. Del historial de conversación que te proporcionaré: 1. SOLO extrae información de los mensajes marcados como 'Usuario', IGNORA completamente los mensajes de 'Bot'. 2. Si el usuario proporciona múltiples valores para el mismo campo (ej: dos números de teléfono), usa el ÚLTIMO que proporcionó o el que parezca correcto según el contexto (ej: si corrige un error). 3. Identifica correcciones explícitas como 'perdón, es 555...' o 'me equivoqué, es...'. 4. Responde un JSON con: nombre, correo, celular (null si no existe). 5. Separa el nombre, celular y correo del usuario. IMPORTANTE: Los mensajes del Bot pueden contener números o emails de ejemplo - IGNÓRALOS COMPLETAMENTE. Solo usa información que el Usuario haya escrito. Ejemplo de salida:\n{ \"nombre\": \"Juan Pérez\", \"correo\": \"juan@mail.com\", \"celular\": \"55123456789\"}",
            messages=[
                {
                    "role": "user",
                    "content": "ANALIZA LA SIGUIENTE CONVERSACIÓN Y EXTRAE LOS DATOS DEL USUARIO:\n\n" + historial_procesado
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "nombre": {"type": ["string", "null"]},
                            "correo": {"type": ["string", "null"]},
                            "celular": {"type": ["string", "null"]},
                        },
                        "required": ["nombre", "correo", "celular"],
                        "additionalProperties": False,
                    },
                }
            }
        )
    except Exception as error:
        logger.warning("Claude extractor error: %s", error)
        if raise_on_error:
            raise
        return {}

    try:
        return json.loads(message.content[0].text)
    except Exception:
        if raise_on_error:
            raise
        return {}
