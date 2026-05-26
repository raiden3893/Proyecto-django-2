"""
Servicio especializado para el flujo de captura de leads guiado por IA.
Este módulo unifica la conversación y la extracción de datos en una sola llamada a la IA.
"""

import json
import logging
from .services import get_ai_chat_response
from .lead_extractor import clean_json_text

logger = logging.getLogger(__name__)

def process_lead_step_with_ai(messages: list, current_lead_state: dict) -> dict:
    """
    Llama a la IA para procesar el siguiente paso de la captura de lead.
    La IA decide qué responder y qué datos extraer basándose únicamente en la conversación actual.
    """
    
    # 1. Definir el prompt maestro que obliga a la IA a seguir el flujo y responder en JSON
    system_prompt = (
        "Eres un asistente experto en captura de leads para BotCoudy. Tu objetivo es obtener: nombre, teléfono, email y disponibilidad. "
        "REGLAS CRÍTICAS DE EXTRACCIÓN:\n"
        "1. Extrae los datos EXACTAMENTE como aparecen escritos por el usuario en su mensaje actual o historial inmediato.\n"
        "2. NO corrijas, NO completes, NO normalices ni modifiques ningún dato. Verbatim absoluto.\n"
        "3. Si el usuario escribe 'Alex', el valor extraído debe ser 'Alex', no 'Alexa'.\n"
        "4. Si el usuario escribe 'Leslie', el valor extraído debe ser 'Leslie'.\n"
        "5. NO uses nombres ni datos de ejemplos anteriores o de otros usuarios que no estén en este historial.\n"
        "6. Si el usuario dice 'REINICIAR' o saluda como nuevo usuario, ignora cualquier dato inferido anteriormente y empieza de cero.\n\n"
        "REGLAS DE CONVERSACIÓN:\n"
        "1. Pide un dato a la vez de forma amable y profesional.\n"
        "2. NUNCA respondas con 'Tus datos ya fueron registrados' a menos que todos los campos del JSON que vas a enviar estén llenos.\n"
        "3. Usa el valor EXACTO capturado en tus respuestas.\n"
        "4. SIEMPRE responde con un objeto JSON válido. NO incluyas texto explicativo.\n\n"
        "FORMATO JSON OBLIGATORIO:\n"
        "{\n"
        "  \"reply\": \"Tu respuesta amable para el usuario\",\n"
        "  \"extracted_data\": {\n"
        "    \"nombre\": \"string verbatim o null\",\n"
        "    \"telefono\": \"string verbatim o null\",\n"
        "    \"email\": \"string verbatim o null\",\n"
        "    \"disponibilidad\": \"string verbatim o null\"\n"
        "  },\n"
        "  \"missing_fields\": [\"lista\", \"de\", \"campos\", \"faltantes\"],\n"
        "  \"is_complete\": true/false,\n"
        "  \"next_field\": \"nombre/telefono/email/disponibilidad/null\"\n"
        "}\n\n"
        f"DATOS CAPTURADOS EN ESTA SESIÓN: {json.dumps(current_lead_state)}"
    )

    # 2. Llamar al servicio base de IA que maneja fallback y logs
    # Usamos use_case='lead_capture_extraction' para permitir personalización desde Admin
    ai_response = get_ai_chat_response(
        messages=messages,
        use_case='lead_capture_extraction',
        system_prompt_override=system_prompt,
        temperature=0.0 # Temperatura baja para máxima consistencia en el JSON
    )

    if not ai_response.get("ok"):
        return ai_response

    # 3. Parsear y validar la respuesta estructurada
    try:
        raw_reply = ai_response.get("reply", "")
        cleaned_json = clean_json_text(raw_reply)
        ai_data = json.loads(cleaned_json)
        
        # Validar estructura mínima requerida
        required_keys = ["reply", "extracted_data", "is_complete"]
        if not all(key in ai_data for key in required_keys):
            raise ValueError("Respuesta de IA no cumple con el esquema requerido")
            
        # Unificar metadatos para el frontend
        ai_data["ok"] = True
        ai_data["provider"] = ai_response.get("provider")
        ai_data["model"] = ai_response.get("model")
        ai_data["fallback_used"] = ai_response.get("fallback_used", False)
        
        return ai_data

    except Exception as e:
        logger.error(f"[LeadAI_Flow] Error parseando respuesta de IA: {e}. Raw: {ai_response.get('reply')}")
        return {
            "ok": False,
            "reply": "Ocurrió un problema al procesar la respuesta inteligente.",
            "error": str(e),
            "raw_reply": ai_response.get("reply")
        }
