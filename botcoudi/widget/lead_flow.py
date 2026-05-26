"""
Motor de flujo por bloques para captura de leads.
El flujo es determinístico y la IA solo extrae el dato esperado por bloque.
"""

import logging
from typing import Any, Dict, List, Optional

from django.db.utils import OperationalError, ProgrammingError

from .models import Lead, WidgetConversation, WidgetFlowBlock

logger = logging.getLogger(__name__)

# Campos obligatorios por defecto si aún no hay configuración activa.
DEFAULT_REQUIRED_FIELDS = ["nombre", "telefono", "email", "disponibilidad"]
BLOCK_TYPE_FIELD_MAP = {
    "name": "nombre",
    "phone": "telefono",
    "email": "email",
    "availability": "disponibilidad",
}

DEFAULT_CONVERSATION_BLOCKS = [
    {
        "name": "Saludo inicial",
        "block_type": "greeting",
        "order": 1,
        "message": "Hola, soy el asistente de BotCoudy. Para empezar, ¿cuál es tu nombre?",
        "required_field": "",
        "validation_type": "ninguno",
        "is_required": False,
        "is_active": True,
    },
    {
        "name": "Nombre",
        "block_type": "name",
        "order": 2,
        "message": "¿Cuál es tu nombre?",
        "required_field": "nombre",
        "validation_type": "texto",
        "is_required": True,
        "is_active": True,
    },
    {
        "name": "Teléfono",
        "block_type": "phone",
        "order": 3,
        "message": "Gracias, {nombre}. ¿Podrías darme tu número de teléfono?",
        "required_field": "telefono",
        "validation_type": "telefono",
        "is_required": True,
        "is_active": True,
    },
    {
        "name": "E-mail",
        "block_type": "email",
        "order": 4,
        "message": "Perfecto. ¿Podrías compartirme tu correo electrónico?",
        "required_field": "email",
        "validation_type": "email",
        "is_required": True,
        "is_active": True,
    },
    {
        "name": "Insistir",
        "block_type": "insist",
        "order": 5,
        "message": "Necesito completar algunos datos para continuar.",
        "required_field": "",
        "validation_type": "ninguno",
        "is_required": False,
        "is_active": True,
    },
    {
        "name": "Disponibilidad",
        "block_type": "availability",
        "order": 6,
        "message": "Gracias. ¿En qué horario prefieres que te contactemos?",
        "required_field": "disponibilidad",
        "validation_type": "horario",
        "is_required": True,
        "is_active": True,
    },
    {
        "name": "Cierre",
        "block_type": "closing",
        "order": 7,
        "message": "Tus datos fueron registrados correctamente. Gracias, {nombre}.",
        "required_field": "",
        "validation_type": "ninguno",
        "is_required": False,
        "is_active": True,
    },
]


def get_default_conversation_blocks() -> List[Dict[str, Any]]:
    return [dict(block) for block in DEFAULT_CONVERSATION_BLOCKS]


def seed_default_conversation_blocks() -> None:
    try:
        existing_count = WidgetFlowBlock.objects.count()
    except (OperationalError, ProgrammingError):
        return

    if existing_count > 0:
        return

    WidgetFlowBlock.objects.bulk_create(
        [
            WidgetFlowBlock(
                name=block["name"],
                block_type=block["block_type"],
                order=block["order"],
                message=block["message"],
                required_field=block["required_field"],
                validation_type=block["validation_type"],
                is_required=block["is_required"],
                is_active=block["is_active"],
            )
            for block in get_default_conversation_blocks()
        ]
    )


def _default_blocks() -> List[Dict[str, Any]]:
    """
    Bloques por defecto si no existen en base de datos.
    """
    return get_default_conversation_blocks()


def get_active_flow_blocks() -> List[Dict[str, Any]]:
    """
    Devuelve los bloques activos del flujo, ordenados por 'order' y 'id'.
    """
    try:
        seed_default_conversation_blocks()
        blocks = list(WidgetFlowBlock.objects.filter(is_active=True).order_by("order", "id"))
        
        if not blocks:
            # Si no hay bloques en la BD, usar los de por defecto
            logger.info("[FLOW] No se encontraron bloques en la BD, usando defaults.")
            return _default_blocks()

        blocks_log = "\n".join([f"{b.order} - {b.name}" for b in blocks])
        logger.info("[FLOW] Bloques activos cargados:\n%s", blocks_log)

    except (OperationalError, ProgrammingError):
        # Si la tabla aún no existe, usar los bloques por defecto.
        logger.warning("[FLOW] Error de BD al cargar bloques, usando defaults.")
        return _default_blocks()

    return [
        {
            "name": block.name,
            "block_type": block.block_type,
            "order": block.order,
            "message": block.message,
            "required_field": block.required_field,
            "validation_type": block.validation_type,
            "is_required": block.is_required,
            "is_active": block.is_active,
        }
        for block in blocks
    ]


def get_initial_lead_data(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Devuelve el estado inicial del lead para la conversación.
    """
    active_blocks = [block for block in blocks if block.get("is_active", True)]
    first_block = active_blocks[0] if active_blocks else {"block_type": "name", "required_field": "nombre"}
    required_fields = get_required_fields(blocks)
    return {
        "nombre": "",
        "telefono": "",
        "email": "",
        "disponibilidad": "",
        "estado": "in_progress",
        "current_block": first_block["block_type"],
        "current_step": get_block_expected_field(first_block) or first_block["block_type"],
        "missing_fields": required_fields.copy(),
        "datos_json": {},
        "is_complete": False,
    }


def get_block_by_type(blocks: List[Dict[str, Any]], block_type: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene un bloque por tipo.
    """
    for block in blocks:
        if block.get("block_type") == block_type:
            return block
    return None


def _render_message(template: str, lead_state: Dict[str, Any]) -> str:
    """
    Renderiza el mensaje del bloque usando datos del lead.
    """
    nombre = lead_state.get("nombre") or "por tu respuesta"
    return (template or "").format(nombre=nombre)


def _active_blocks_sorted(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filtra bloque activos manteniendo el orden ya establecido en la lista.
    """
    return [block for block in blocks if block.get("is_active", True)]


def get_block_expected_field(block: Dict[str, Any]) -> str:
    required_field = (block.get("required_field") or "").strip()
    if required_field:
        return required_field
    return BLOCK_TYPE_FIELD_MAP.get((block.get("block_type") or "").strip(), "")


def get_first_action_block(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    active_blocks = _active_blocks_sorted(blocks)
    if not active_blocks:
        return {}

    for block in active_blocks:
        required_field = get_block_expected_field(block)
        if required_field:
            return block

    return active_blocks[0]


def get_first_missing_required_block(blocks: List[Dict[str, Any]], lead_state: Dict[str, Any]) -> Dict[str, Any]:
    missing_fields = set(get_missing_fields(lead_state, blocks))
    if not missing_fields:
        return {}

    for block in _active_blocks_sorted(blocks):
        required_field = get_block_expected_field(block)
        if required_field and required_field in missing_fields:
            return block
    return {}


def get_required_fields(blocks: List[Dict[str, Any]]) -> List[str]:
    required_fields: List[str] = []
    for block in _active_blocks_sorted(blocks):
        if not block.get("is_required", True):
            continue
        required_field = get_block_expected_field(block)
        if not required_field or required_field in required_fields:
            continue
        required_fields.append(required_field)
    return required_fields or DEFAULT_REQUIRED_FIELDS.copy()


def _is_valid_value(field: str, value: str) -> bool:
    """
    Validación mínima: solo evitar valores vacíos.
    """
    return bool(value and value.strip())


def apply_ai_result_to_state(
    lead_state: Dict[str, Any],
    ai_result: Dict[str, Any],
    blocks: List[Dict[str, Any]] | None = None,
    expected_field: str = "",
) -> Dict[str, Any]:
    """
    Actualiza el estado con la respuesta de la IA si es válida.
    """
    if not ai_result or not ai_result.get("ok"):
        return lead_state

    lead_data = ai_result.get("lead_data")
    if not isinstance(lead_data, dict):
        return lead_state

    updated_state = dict(lead_state)
    datos_json = updated_state.get("datos_json")
    if not isinstance(datos_json, dict):
        datos_json = {}
    updated_state["datos_json"] = datos_json

    for field in DEFAULT_REQUIRED_FIELDS:
        if expected_field and field != expected_field:
            continue
        value = lead_data.get(field)
        if isinstance(value, str):
            value = value.strip()
            if value:
                updated_state[field] = value
        elif value is None:
            continue

    current_step = ai_result.get("current_step")
    if isinstance(current_step, str) and current_step.strip():
        normalized_step = current_step.strip()
        if not expected_field or normalized_step == expected_field:
            updated_state["current_step"] = normalized_step

    updated_state["missing_fields"] = get_missing_fields(updated_state, blocks)
    updated_state["is_complete"] = len(updated_state["missing_fields"]) == 0
    updated_state["estado"] = "completed" if updated_state["is_complete"] else "in_progress"

    updated_state["datos_json"].update({
        "last_ai_provider": ai_result.get("provider"),
        "last_ai_model": ai_result.get("model"),
        "last_ai_reply": ai_result.get("reply"),
    })
    return updated_state


def get_missing_fields(lead_state: Dict[str, Any], blocks: List[Dict[str, Any]] | None = None) -> List[str]:
    """
    Devuelve los campos obligatorios que aún faltan.
    """
    required_fields = get_required_fields(blocks or [])
    return [field for field in required_fields if not lead_state.get(field)]


def is_lead_complete(lead_state: Dict[str, Any], blocks: List[Dict[str, Any]] | None = None) -> bool:
    """
    Determina si el lead tiene todos los campos obligatorios.
    """
    return len(get_missing_fields(lead_state, blocks)) == 0


def get_next_block(
    blocks: List[Dict[str, Any]],
    current_block: Dict[str, Any],
    lead_state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Determina el siguiente bloque a mostrar según la configuración activa.
    """
    active_blocks = _active_blocks_sorted(blocks)
    if not active_blocks:
        return current_block or {}

    if not current_block or current_block not in active_blocks:
        return active_blocks[0]

    current_required = get_block_expected_field(current_block)
    if current_required and not lead_state.get(current_required):
        return current_block

    missing_fields = set(get_missing_fields(lead_state, blocks))
    current_index = active_blocks.index(current_block)
    for block in active_blocks[current_index + 1 :]:
        if block.get("block_type") == "closing" and missing_fields:
            continue
        return block

    return current_block


def get_current_block(blocks: List[Dict[str, Any]], lead_state: Dict[str, Any]) -> Dict[str, Any]:
    active_blocks = _active_blocks_sorted(blocks)
    if not active_blocks:
        return {}

    current_block_type = (lead_state or {}).get("current_block")
    if current_block_type:
        for block in active_blocks:
            if block.get("block_type") == current_block_type:
                if block.get("block_type") == "closing" and get_missing_fields(lead_state, blocks):
                    break
                return block

    return active_blocks[0]


def build_reply(
    current_block: Dict[str, Any],
    next_block: Dict[str, Any],
    lead_state: Dict[str, Any],
) -> str:
    """
    Construye la respuesta del bot basada en el bloque actual o el siguiente.
    """
    if next_block and next_block != current_block:
        return _render_message(next_block.get("message", ""), lead_state)
    return _render_message(current_block.get("message", ""), lead_state)


def finalize_lead(conversation: WidgetConversation) -> Lead | None:
    """
    Persiste el lead final cuando el flujo está completo.
    """
    lead_state = conversation.lead_state or {}
    blocks = get_active_flow_blocks()
    if not is_lead_complete(lead_state, blocks):
        return None

    lead, _ = Lead.objects.update_or_create(
        conversation=conversation,
        defaults={
            "nombre": lead_state.get("nombre"),
            "telefono": lead_state.get("telefono"),
            "email": lead_state.get("email"),
            "disponibilidad": lead_state.get("disponibilidad"),
            "estado": "completed",
            "fuente": "widget",
            "metadata": {
                "captured_from": "widget",
                "datos_json": lead_state.get("datos_json", {}),
            },
        },
    )
    return lead
