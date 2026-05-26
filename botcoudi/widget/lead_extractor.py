"""
Extractor de datos de lead usando IA (OpenAI/Claude) con fallback.
La IA devuelve un JSON canónico para actualizar el estado del lead.
"""

import json
import logging
from typing import Any, Dict, List

from django.db.utils import OperationalError, ProgrammingError

from ai_manage.models import AIPromptTemplate
from .services import get_ai_chat_response

logger = logging.getLogger(__name__)

LEAD_FIELDS = ("nombre", "telefono", "email", "disponibilidad")
ALLOWED_CURRENT_STEPS = set(LEAD_FIELDS) | {"completado", "closing"}

LEAD_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "lead_data": {
            "type": "object",
            "properties": {
                "nombre": {"type": ["string", "null"]},
                "telefono": {"type": ["string", "null"]},
                "email": {"type": ["string", "null"]},
                "disponibilidad": {"type": ["string", "null"]},
            },
            "required": list(LEAD_FIELDS),
            "additionalProperties": False,
        },
        "current_step": {"type": "string"},
        "completed": {"type": "boolean"},
    },
    "required": ["reply", "lead_data", "current_step", "completed"],
    "additionalProperties": True,
}


def clean_json_text(text: str) -> str:
    """Elimina bloques markdown y texto extra para obtener solo el JSON."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text[3:].lstrip()
        if text.startswith("json"):
            text = text[4:].lstrip()
        if text.endswith("```"):
            text = text[:-3].rstrip()

    brace_index = text.find("{")
    last_brace = text.rfind("}")
    if brace_index != -1 and last_brace != -1 and last_brace > brace_index:
        text = text[brace_index:last_brace + 1]

    return text.strip()


def _format_history(history: List[Dict[str, str]], limit: int = 6) -> str:
    """Formatea el historial reciente para el prompt de extracción."""
    if not history:
        return ""
    sliced = history[-limit:]
    return "\n".join(f"{item.get('role')}: {item.get('content')}" for item in sliced)


def _safe_format_prompt(template: str, context: Dict[str, Any], fallback: str) -> str:
    try:
        formatted = template
        for key, value in context.items():
            formatted = formatted.replace(f"{{{key}}}", str(value))
        return formatted
    except Exception as error:
        logger.warning("[AI_MANAGER] Plantilla de prompt inválida, usando fallback: %s", error)
        return fallback


def _build_schema_contract() -> str:
    return (
        "Responde SOLO con un JSON válido, sin markdown ni texto adicional.\n"
        "Esquema exacto:\n"
        "{\n"
        '  "reply": "texto conversacional para el usuario",\n'
        '  "lead_data": {\n'
        '    "nombre": "string o null",\n'
        '    "telefono": "string o null",\n'
        '    "email": "string o null",\n'
        '    "disponibilidad": "string o null"\n'
        "  },\n"
        '  "current_step": "nombre | telefono | email | disponibilidad | completado | closing",\n'
        '  "completed": true\n'
        "}\n"
        "Reglas críticas:\n"
        "- No inventes datos.\n"
        "- No corrijas nombres.\n"
        "- No normalices formatos.\n"
        "- Mantén exactamente lo que el usuario escribió cuando el dato exista.\n"
        "- Usa null cuando un campo aún no haya sido capturado.\n"
    )


def _validate_canonical_payload(payload: Dict[str, Any]) -> bool:
    required_keys = {"reply", "lead_data", "current_step", "completed"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload.keys()):
        return False

    if not isinstance(payload.get("reply"), str) or not payload.get("reply").strip():
        return False

    lead_data = payload.get("lead_data")
    if not isinstance(lead_data, dict):
        return False

    for field in LEAD_FIELDS:
        if field not in lead_data:
            return False
        value = lead_data.get(field)
        if value is not None and not isinstance(value, str):
            return False

    current_step = payload.get("current_step")
    if not isinstance(current_step, str) or not current_step.strip():
        return False
    current_step = current_step.strip()
    if current_step not in ALLOWED_CURRENT_STEPS:
        return False

    if not isinstance(payload.get("completed"), bool):
        return False

    return True


def extract_field_with_ai(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    current_block: Dict[str, Any],
    expected_field: str,
    lead_state: Dict[str, Any],
) -> Dict[str, Any]:
    logger.info("[AI_MANAGER] Analizando mensaje para el Bloque actual: %s (Campo: %s)", current_block.get('name'), expected_field)
    
    """
    Solicita a la IA que devuelva el reply conversacional y el estado del lead.
    """
    history_text = _format_history(conversation_history)
    block_name = current_block.get("name", "")
    block_type = current_block.get("block_type", "")
    block_message = current_block.get("message", "")
    block_validation = current_block.get("validation_type", "ninguno")
    block_order = current_block.get("order", "")
    schema_contract = _build_schema_contract()
    flow_context = (
        f"Contexto del bloque actual:\n"
        f"- nombre: {block_name}\n"
        f"- tipo: {block_type}\n"
        f"- orden: {block_order}\n"
        f"- mensaje: {block_message}\n"
        f"- campo relacionado: {expected_field}\n"
        f"- validación: {block_validation}\n"
        f"- obligatorio: {'sí' if current_block.get('is_required') else 'no'}\n"
    )

    default_system_prompt = (
        "Eres un asistente de captación de leads para BotCoudy. "
        "Debes mantener una conversación natural y actualizar el estado del lead siguiendo el bloque actual. "
        "No inventes información, no corrijas nombres y no normalices formatos. "
        f"{schema_contract}"
    )

    default_user_prompt = (
        f"Bloque actual: {block_name} ({block_type})\n"
        f"Orden del bloque: {block_order}\n"
        f"Mensaje del bloque: {block_message}\n"
        f"Campo esperado: {expected_field}\n"
        f"Validación: {block_validation}\n"
        f"Obligatorio: {'sí' if current_block.get('is_required') else 'no'}\n"
        f"Estado actual del lead: {json.dumps(lead_state, ensure_ascii=False)}\n"
        f"Historial reciente:\n{history_text}\n\n"
        f"Último mensaje del usuario:\n{user_message}\n\n"
        f"{schema_contract}"
    )

    try:
        prompt_template = (
            AIPromptTemplate.objects.filter(use_case="lead_capture_extraction", is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if prompt_template:
            system_prompt = (prompt_template.system_prompt or default_system_prompt).strip()
            if schema_contract not in system_prompt:
                system_prompt = f"{system_prompt}\n\n{schema_contract}"

            user_prompt_source = prompt_template.user_prompt_template or default_user_prompt
            user_prompt = _safe_format_prompt(
                user_prompt_source,
                {
                    "block_name": block_name,
                    "block_type": block_type,
                    "expected_field": expected_field,
                    "lead_state": json.dumps(lead_state, ensure_ascii=False),
                    "history": history_text,
                    "user_message": user_message,
                },
                default_user_prompt,
            )
            if flow_context not in user_prompt:
                user_prompt = f"{flow_context}\n{user_prompt}"
            if schema_contract not in user_prompt:
                user_prompt = f"{user_prompt}\n\n{schema_contract}"
        else:
            system_prompt = default_system_prompt
            user_prompt = default_user_prompt
    except (OperationalError, ProgrammingError):
        system_prompt = default_system_prompt
        user_prompt = default_user_prompt

    def _json_validator(raw_text: str) -> bool:
        cleaned = clean_json_text(raw_text)
        parsed = json.loads(cleaned)
        return _validate_canonical_payload(parsed)

    ai_result = get_ai_chat_response(
        messages=[{"role": "user", "content": user_prompt}],
        use_case="lead_capture_extraction",
        system_prompt_override=system_prompt,
        temperature=0,
        response_schema=LEAD_RESPONSE_SCHEMA,
        response_validator=_json_validator,
    )

    if not ai_result.get("ok"):
        return {
            "ok": False,
            "error": ai_result.get("error") or "Proveedor de IA no disponible.",
            "provider": ai_result.get("provider"),
            "model": ai_result.get("model"),
            "fallback_used": ai_result.get("fallback_used", False),
        }

    try:
        raw_reply = ai_result.get("reply", "")
        cleaned_json = clean_json_text(raw_reply)
        parsed = json.loads(cleaned_json)
        logger.info("[AI_MANAGER] JSON parseado correctamente")
    except Exception as error:
        logger.error("[AI_MANAGER] Falló el parser JSON: %s", error)
        return {
            "ok": False,
            "error": f"JSON inválido: {error}",
            "provider": ai_result.get("provider"),
            "model": ai_result.get("model"),
            "fallback_used": ai_result.get("fallback_used", False),
        }

    if not _validate_canonical_payload(parsed):
        return {
            "ok": False,
            "error": "Respuesta de IA no cumple el esquema requerido.",
            "provider": ai_result.get("provider"),
            "model": ai_result.get("model"),
            "fallback_used": ai_result.get("fallback_used", False),
        }

    lead_data = {field: parsed["lead_data"].get(field) for field in LEAD_FIELDS}
    current_step = parsed["current_step"].strip()

    logger.info("[AI_MANAGER] Datos extraídos por %s: %s", ai_result.get("provider"), json.dumps(lead_data))
    missing = [f for f in LEAD_FIELDS if not lead_data.get(f)]
    logger.info("[AI_MANAGER] Siguiente paso sugerido: %s (Faltan: %s)", current_step, missing)

    return {
        "ok": True,
        "reply": parsed["reply"].strip(),
        "lead_data": lead_data,
        "current_step": current_step,
        "completed": bool(parsed["completed"]),
        "valid": True,
        "field": current_step if current_step in LEAD_FIELDS else None,
        "value": lead_data.get(current_step) if current_step in LEAD_FIELDS else None,
        "needs_retry": False,
        "reason": "Respuesta válida con esquema canónico.",
        "provider": ai_result.get("provider"),
        "model": ai_result.get("model"),
        "fallback_used": ai_result.get("fallback_used", False),
    }
