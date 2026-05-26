import json

import anthropic
from django.conf import settings

from crm.utils import validador_formulario_spam as spam_utils


def validar_formulario_web_claude(
    web_content: dict,
    api_key: str,
    lista_negra_emails: list = None,
    historial_spam: list = None,
    ejemplos_spam: list = None
) -> dict:
    """
    Valida y clasifica un envío de formulario web usando Anthropic (Claude).

    Args:
        web_content: Diccionario con los campos del formulario
        api_key: API key de Anthropic
        lista_negra_emails: Lista de correos bloqueados (catálogo manual)
        historial_spam: Lista de mensajes previamente marcados como spam
        ejemplos_spam: Lista de ejemplos documentados de spam (desde ejemplos_spam.json)

    Returns:
        dict con:
            - status: -1 (spam), 0 (dudoso), 1 (válido)
            - datos_extraidos: {nombre, correo, celular, mensaje}
            - justificacion: Razón de la clasificación
    """
    lista_negra_emails = lista_negra_emails or []
    historial_spam = historial_spam or []
    ejemplos_spam = ejemplos_spam or []

    # Extraer email del formulario para verificación rápida
    email_formulario = spam_utils._extraer_email_de_contenido(web_content)

    # Verificación rápida contra lista negra (soporta emails y dominios)
    if email_formulario and spam_utils.email_en_lista_negra(email_formulario, lista_negra_emails):
        return {
            'status': spam_utils.STATUS_SPAM,
            'datos_extraidos': spam_utils._extraer_datos_basicos(web_content),
            'justificacion': f'Email {email_formulario} está en lista negra de correos bloqueados.'
        }

    # Verificación de dominio sospechoso/temporal
    if email_formulario and spam_utils.es_dominio_sospechoso(email_formulario):
        return {
            'status': spam_utils.STATUS_DUDOSO,
            'datos_extraidos': spam_utils._extraer_datos_basicos(web_content),
            'justificacion': f'Email {email_formulario} pertenece a un dominio de correo temporal/desechable.'
        }

    # Verificación de mensaje muy corto o genérico
    # NOTA: El campo mensaje es OPCIONAL. Solo marcar como dudoso si el campo
    # existe y tiene contenido muy corto/genérico. Si no existe o está vacío,
    # se deja pasar a IA para evaluar con los demás datos (nombre, email, teléfono).
    mensaje_corto = spam_utils._extraer_mensaje_de_contenido(web_content)
    if mensaje_corto and 0 < len(mensaje_corto.strip()) <= 15:
        return {
            'status': spam_utils.STATUS_DUDOSO,
            'datos_extraidos': spam_utils._extraer_datos_basicos(web_content),
            'justificacion': f'Mensaje muy corto o genérico: "{mensaje_corto.strip()}". Se requiere más contexto para validar.'
        }

    # Detección programática contra ejemplos documentados de spam
    resultado_ejemplos = spam_utils.detectar_spam_por_ejemplos(web_content, ejemplos_spam)
    if resultado_ejemplos:
        return resultado_ejemplos

    client = anthropic.Anthropic(api_key=api_key)

    # Construir contexto de spam para el modelo
    ejemplos_spam_texto = spam_utils._construir_contexto_ejemplos_spam(ejemplos_spam)
    contexto_spam = ""
    if historial_spam:
        historial_reciente = historial_spam[:10]
        contexto_spam = "\n\nEJEMPLOS DE SPAM PREVIOS (para referencia):\n"
        for i, spam in enumerate(historial_reciente, 1):
            contexto_spam += f"{i}. {spam[:200]}...\n" if len(spam) > 200 else f"{i}. {spam}\n"

    contenido_str = json.dumps(web_content, ensure_ascii=False, indent=2)

    message = client.messages.create(
        model=settings.AI_SPAM_DETECTOR_MODEL,
        max_tokens=1200,
        system="Eres un clasificador de formularios web especializado en detección de spam.\n\n Tu tarea es:\n 1. EXTRAER y NORMALIZAR los datos del usuario: nombre, correo, celular, mensaje\n 2. CLASIFICAR el envío con un status:\n    -1 = SPAM: Mensaje malicioso, publicidad, enlaces sospechosos, texto incoherente/repetitivo\n    0 = DUDOSO: Mensaje incompleto, ambiguo, datos faltantes, patrones sospechosos\n    1 = VÁLIDO: Mensaje legítimo, coherente, intención clara, datos consistentes\n 3. JUSTIFICAR brevemente tu decisión\n\n CRITERIOS DE SPAM:\n - Repetición excesiva de palabras o enlaces\n - Dominios de correo sospechosos o temporales (ej: tempmail, guerrilla, 10minutemail, othao, loquesea)\n - Dominios de email muy cortos o con nombres aleatorios (ej: abc.com, xyz.net, othao.com)\n - Mensajes genéricos sin contexto específico\n - Incoherencia entre nombre, correo y mensaje\n - Texto sin sentido o generado automáticamente\n - IMPORTANTE: Nombres con números (ej: 'Juan123', 'tester13', 'user456') = SPAM\n - IMPORTANTE: Teléfono como texto en lugar de números (ej: 'lo que sea', 'ninguno', 'no tengo') = SPAM\n - IMPORTANTE: Teléfono con letras mezcladas o espacios excesivos = SPAM\n - IMPORTANTE: Propuestas comerciales no solicitadas = SPAM. Incluye:\n   * Ofertas de servicios SEO, marketing digital, afiliados, comisiones\n   * Propuestas de colaboración comercial de desconocidos\n   * Venta de herramientas, software o servicios (ej: 'Book In A Day', 'Ghost Pages', 'Video Script Pro')\n   * Mensajes con enlaces a plataformas externas ofreciendo productos/servicios\n   * Mensajes que mencionan el dominio del destinatario como gancho de venta\n - IMPORTANTE: Contenido para adultos, apuestas, sorteos falsos, citas = SPAM\n - IMPORTANTE: Mensajes con enlaces UNSUBSCRIBE o 'cancelar suscripción' = SPAM (indica envío masivo)\n - IMPORTANTE: Mensajes en idioma diferente al del servicio/negocio sin relación = SPAM\n - IMPORTANTE: Ciudad del prospecto en otro país sin relación con el servicio = señal de SPAM\n\n CRITERIOS DE DUDOSO (marcar como 0):\n - Nombres de prueba sin números (ej: 'test', 'prueba', 'asdf', 'qwerty', 'demo')\n - Nombres que parecen tecleados al azar (ej: 'Rodohdhsa', 'asdfjkl', 'qwertyuiop', 'zxcvbnm')\n - Nombres con patrones de teclado o letras consecutivas sin sentido\n - Nombres muy cortos (1-2 caracteres) o solo iniciales\n - Nombres que no parecen nombres reales en ningún idioma\n - Teléfono muy corto (menos de 7 dígitos) o muy largo (más de 15 dígitos)\n - Datos incompletos (falta nombre, correo o teléfono)\n\n IMPORTANTE SOBRE EL CAMPO MENSAJE:\n - El campo 'mensaje' es OPCIONAL en muchos formularios.\n - Si no hay campo mensaje o está vacío, NO es motivo para marcar como DUDOSO.\n - Evalúa con los demás datos (nombre, correo, teléfono). Si son coherentes y legítimos, marca como VÁLIDO.\n - Solo marca como DUDOSO si el mensaje EXISTE pero es muy corto/genérico (ej: 'Hola', 'Info', 'test').\n\n CRITERIOS DE MENSAJE VÁLIDO:\n - Intención clara del usuario (o ausencia de mensaje si el formulario no lo requiere)\n - Coherencia en los datos proporcionados\n - Mensaje contextual y específico (cuando existe)\n - Email con dominio legítimo\n - Nombre que sea un nombre real reconocible (en español, inglés u otro idioma)\n - NO nombres aleatorios o sin sentido como 'Rodohdhsa', 'Xyzabc', 'Fghijk'\n - Teléfono con solo números (puede tener + al inicio o guiones)\n\n Responde SOLO con un JSON válido:\n {\n \"status\": -1 | 0 | 1,\n  \"datos_extraidos\": {\n    \"nombre\": \"string o null\",\n    \"correo\": \"string o null\",\n    \"celular\": \"string o null\",\n    \"mensaje\": \"string o null\"\n  },\n  \"justificacion\": \"razón breve de la clasificación\"\n}\n" + ejemplos_spam_texto + "\n" + contexto_spam,
        messages=[
            {
                "role": "user",
                "content": "Analiza y clasifica este envío de formulario web:\n\n" + contenido_str
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "integer"},
                        "datos_extraidos": {
                            "type": "object",
                            "properties": {
                                "nombre": {"type": ["string", "null"]},
                                "correo": {"type": ["string", "null"]},
                                "celular": {"type": ["string", "null"]},
                                "mensaje": {"type": ["string", "null"]}
                            },
                            "required": ["nombre", "correo", "celular", "mensaje"],
                            "additionalProperties": False
                        },
                        "justificacion": {"type": "string"}
                    },
                "required": ["status", "datos_extraidos", "justificacion"],
                "additionalProperties": False
                },
            }
        }
    )

    try:
        resultado = json.loads(message.content[0].text)

        # Validar estructura de respuesta
        if 'status' not in resultado:
            resultado['status'] = spam_utils.STATUS_DUDOSO
        if 'datos_extraidos' not in resultado:
            resultado['datos_extraidos'] = spam_utils._extraer_datos_basicos(web_content)
        if 'justificacion' not in resultado:
            resultado['justificacion'] = 'Clasificación automática sin justificación'

        # Asegurar que status sea un entero válido
        resultado['status'] = int(resultado['status'])
        if resultado['status'] not in [spam_utils.STATUS_SPAM, spam_utils.STATUS_DUDOSO, spam_utils.STATUS_VALIDO]:
            resultado['status'] = spam_utils.STATUS_DUDOSO

        return resultado

    except json.JSONDecodeError:
        return {
            'status': spam_utils.STATUS_DUDOSO,
            'datos_extraidos': spam_utils._extraer_datos_basicos(web_content),
            'justificacion': 'Error al procesar respuesta de IA - clasificado como dudoso'
        }
    except Exception as e:
        return {
            'status': spam_utils.STATUS_DUDOSO,
            'datos_extraidos': spam_utils._extraer_datos_basicos(web_content),
            'justificacion': f'Error en validación: {str(e)}'
        }
