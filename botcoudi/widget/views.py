import json
import time
import logging
from django.shortcuts import render
from django.forms import modelformset_factory
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .forms import WidgetFlowBlockForm
from .models import WidgetConversation, WidgetMessage, WidgetFlowBlock
from .lead_extractor import extract_field_with_ai
from .lead_flow import (
    apply_ai_result_to_state,
    build_reply,
    finalize_lead,
    get_active_flow_blocks,
    get_block_expected_field,
    get_block_by_type,
    get_first_action_block,
    get_initial_lead_data,
    get_current_block,
    get_missing_fields,
    get_next_block,
    seed_default_conversation_blocks,
    is_lead_complete,
)

logger = logging.getLogger(__name__)
GREETING_RESET_MESSAGES = {
    "hola",
    "holi",
    "hello",
    "hi",
    "buenas",
    "buenos dias",
    "buen dia",
}

def _block_to_view_data(block):
    return {
        "order": block.order,
        "name": block.name,
        "type": block.block_type,
        "description": block.message,
        "field": block.required_field or "no_aplica",
        "validation_type": block.validation_type,
        "status": "Activo" if block.is_active else "Inactivo",
        "is_required": block.is_required,
        "is_active": block.is_active,
    }

def prueba_widget(request):
    """Página de prueba del widget."""
    blocks = get_active_flow_blocks()
    initial_bot_message = blocks[0].get("message") if blocks else "Hola, soy el asistente de BotCoudy. Para empezar, ¿cuál es tu nombre?"
    return render(request, 'widget/prueba_widget.html', {
        "initial_bot_message": initial_bot_message,
    })


def configuracion_conversacion(request):
    """Página visual para revisar los bloques de conversación."""
    seed_default_conversation_blocks()
    BlockFormSet = modelformset_factory(
        WidgetFlowBlock,
        form=WidgetFlowBlockForm,
        extra=0,
        can_delete=False,
    )

    blocks_qs = WidgetFlowBlock.objects.order_by("order", "id")
    saved = False

    if request.method == "POST":
        delete_block_id = request.POST.get("delete_block_id")
        action = request.POST.get("action")

        if delete_block_id:
            WidgetFlowBlock.objects.filter(pk=delete_block_id).delete()
            saved = True
            blocks_qs = WidgetFlowBlock.objects.order_by("order", "id")
            formset = BlockFormSet(queryset=blocks_qs)
        elif action == "add_block":
            max_order = WidgetFlowBlock.objects.order_by("-order", "-id").values_list("order", flat=True).first() or 0
            WidgetFlowBlock.objects.create(
                name="Nuevo mensaje",
                block_type=WidgetFlowBlock.BlockType.CUSTOM,
                order=max_order + 1,
                message="Escribe aqui el mensaje del nuevo bloque.",
                required_field="",
                validation_type=WidgetFlowBlock.ValidationType.NONE,
                is_required=False,
                is_active=True,
            )
            saved = True
            blocks_qs = WidgetFlowBlock.objects.order_by("order", "id")
            formset = BlockFormSet(queryset=blocks_qs)
        else:
            formset = BlockFormSet(request.POST, queryset=blocks_qs)
            if formset.is_valid():
                formset.save()
                saved = True
                blocks_qs = WidgetFlowBlock.objects.order_by("order", "id")
                formset = BlockFormSet(queryset=blocks_qs)
    else:
        formset = BlockFormSet(queryset=blocks_qs)

    return render(request, 'widget/configuracion_conversacion.html', {
        "formset": formset,
        "conversation_blocks": [_block_to_view_data(block) for block in blocks_qs],
        "saved": saved,
    })

@csrf_exempt
def api_mensaje(request):
    """
    Endpoint principal para recibir mensajes del widget.
    Flujo guiado por bloques con extracción vía IA (OpenAI/Claude).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        body_session_id = data.get('session_id')
        
        if not user_message:
            return JsonResponse({'ok': False, 'error': 'Mensaje vacío'}, status=400)

        # 1. Obtener session_id (Prioridad body -> session cookie)
        session_id = body_session_id or request.session.session_key
        if not session_id:
            request.session.create()
            session_id = request.session.session_key
        
        # 2. Obtener conversación
        conversation = WidgetConversation.objects.filter(session_id=session_id).first()

        # REGLA DE REINICIO O NUEVA SESIÓN POR COMPLETADO
        force_new = False
        if user_message.upper() == "REINICIAR":
            logger.info(f"[Session] Comando REINICIAR detectado para {session_id}")
            force_new = True
        elif conversation and conversation.lead_state.get("is_complete"):
            logger.info(f"[Session] Conversación completada detectada ({session_id}), creando nueva sesión limpia.")
            force_new = True

        if force_new:
            # Generar un nuevo ID de sesión para romper el vínculo con datos anteriores
            import uuid
            session_id = f"sess_{uuid.uuid4().hex[:8]}_{int(time.time())}"
            conversation = WidgetConversation.objects.create(session_id=session_id)
            logger.info(f"[Session] Nueva conversación creada tras reset/completado: {session_id}")
        elif not conversation:
            conversation = WidgetConversation.objects.create(session_id=session_id)
            logger.info(f"[Session] Nueva conversación iniciada: {session_id}")
        
        # 3. Guardar mensaje del usuario (Historial)
        WidgetMessage.objects.create(conversation=conversation, role='user', content=user_message)

        # 4. Obtener bloques activos del flujo
        blocks = get_active_flow_blocks()
        if blocks:
            # El log ahora se genera dentro de get_active_flow_blocks
            pass

        # 4.1 Si el usuario pidió reiniciar, responder con el inicio del flujo
        if user_message.upper() == "REINICIAR":
            lead_state = get_initial_lead_data(blocks)
            conversation.lead_state = lead_state
            conversation.save()

            first_block = blocks[0] if blocks else get_first_action_block(blocks)
            reply_text = (first_block or {}).get("message", "Conversación reiniciada.")
            WidgetMessage.objects.create(
                conversation=conversation,
                role='assistant',
                content=reply_text,
                provider=None,
                model_name=None,
                metadata_json={"flow_reset": True}
            )

            return JsonResponse({
                "ok": True,
                "reply": reply_text,
                "provider": None,
                "model": None,
                "provider_label": "",
                "provider_source": "flow",
                "fallback_used": False,
                "conversation_id": session_id,
                "lead_state": lead_state,
                "lead_saved": False
            })

        # 5. Obtener estado actual del lead (Siempre debe empezar limpio si la conversación es nueva)
        lead_state = conversation.lead_state
        if not lead_state:
            lead_state = get_initial_lead_data(blocks)
            logger.info(f"[LeadState] Estado inicializado limpio para {session_id}")
        elif not lead_state.get("current_block"):
            # Asegurar compatibilidad con estados antiguos sin bloques.
            lead_state["current_block"] = blocks[0].get("block_type")
            lead_state["current_step"] = get_block_expected_field(blocks[0]) or blocks[0].get("block_type")

        normalized_user_message = user_message.strip().lower()
        first_block = blocks[0] if blocks else {}
        if (
            normalized_user_message in GREETING_RESET_MESSAGES
            and first_block
            and lead_state.get("current_block")
            and lead_state.get("current_block") != first_block.get("block_type")
        ):
            lead_state = get_initial_lead_data(blocks)
            conversation.lead_state = lead_state
            conversation.save(update_fields=["lead_state", "updated_at"])
            logger.info("[FLOW] Reinicio automatico aplicado por saludo en sesion desfasada.")

        # 6. Obtener historial reciente (incluyendo el último mensaje del usuario)
        history_qs = WidgetMessage.objects.filter(conversation=conversation).order_by('-created_at')[:8]
        history = [{"role": msg.role, "content": msg.content} for msg in reversed(history_qs)]

        # 7. Determinar bloque actual y campo esperado
        current_block = get_current_block(blocks, lead_state) or (blocks[0] if blocks else {})
        expected_field = get_block_expected_field(current_block)
        logger.info("[FLOW] Bloque actual: %s", current_block.get("name"))
        logger.info("[FLOW] Campo esperado: %s", expected_field or "no_aplica")

        # 8. Llamar a la IA para extraer el campo esperado del bloque
        ai_result = None
        if expected_field:
            ai_result = extract_field_with_ai(
                user_message=user_message,
                conversation_history=history,
                current_block=current_block,
                expected_field=expected_field,
                lead_state=lead_state,
            )

            if not ai_result.get("ok"):
                return JsonResponse({
                    "ok": False,
                    "reply": "Lo siento, por el momento no fue posible procesar tu mensaje con los proveedores de IA configurados.",
                    "provider": None,
                    "model": None,
                    "provider_label": "IA no disponible",
                    "provider_source": "error",
                    "fallback_used": True,
                    "lead_state": lead_state
                })

            # 9. Aplicar el dato extraído al estado del lead (sin reglas locales de extracción)
            lead_state = apply_ai_result_to_state(lead_state, ai_result, blocks, expected_field=expected_field)
            logger.info("[FLOW] Dato extraído: %s", ai_result.get("value") or "")
            logger.info("[AI_MANAGER] Proveedor usado: %s", ai_result.get("provider"))
            logger.info("[AI_MANAGER] Modelo usado: %s", ai_result.get("model"))

        # 10. Actualizar campos de control del flujo
        lead_state["missing_fields"] = get_missing_fields(lead_state, blocks)
        lead_state["is_complete"] = is_lead_complete(lead_state, blocks)
        lead_state["estado"] = "completed" if lead_state["is_complete"] else "in_progress"

        # 11. Determinar el siguiente bloque según el estado actualizado
        if lead_state["is_complete"]:
            next_block = get_block_by_type(blocks, "closing") or current_block
        else:
            next_block = get_next_block(blocks, current_block, lead_state)

        reply_text = build_reply(current_block, next_block, lead_state)
        logger.info("[FLOW] Siguiente bloque: %s", next_block.get("name"))

        # 12. Actualizar el bloque actual en el estado
        lead_state["current_block"] = next_block.get("block_type", current_block.get("block_type"))
        lead_state["current_step"] = get_block_expected_field(next_block) or next_block.get("block_type")

        # 13. Guardar estado actualizado en la conversación
        conversation.lead_state = lead_state
        conversation.save()
        logger.info(f"[LeadState] Estado actualizado: {lead_state}")

        # 14. Persistir Lead Final si el flujo está completo
        lead_saved = False
        if lead_state["is_complete"]:
            finalize_lead(conversation)
            lead_saved = True
            logger.info(f"[LeadSaved] Lead persistido en tabla final para {session_id}")

        # 15. Guardar mensaje del asistente en el historial
        WidgetMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=reply_text,
            provider=(ai_result or {}).get("provider"),
            model_name=(ai_result or {}).get("model"),
            metadata_json={
                "ai_data": ai_result,
                "fallback_used": (ai_result or {}).get("fallback_used", False)
            }
        )

        # 16. Responder al frontend con toda la información necesaria
        provider = (ai_result or {}).get("provider")
        
        # Extraer solo los campos de datos para la tarjeta del lead
        lead_data_only = {
            "nombre": lead_state.get("nombre"),
            "telefono": lead_state.get("telefono"),
            "email": lead_state.get("email"),
            "disponibilidad": lead_state.get("disponibilidad"),
        }

        response_data = {
            "ok": True, 
            "reply": reply_text,
            "provider": provider,
            "model": (ai_result or {}).get("model"),
            "provider_label": str(provider or "").upper(),
            "provider_source": "ai" if provider else "flow",
            "fallback_used": (ai_result or {}).get("fallback_used", False),
            "conversation_id": session_id,
            "lead_data": lead_data_only,
            "lead_state": lead_state,
            "current_step": lead_state.get("current_step"),
            "status": lead_state.get("estado"),
            "lead_saved": lead_saved
        }
        
        logger.info("[WidgetAPI] lead_data enviado al frontend: %s", lead_data_only)
        return JsonResponse(response_data)

    except Exception as e:
        logger.exception(f"[WidgetAPI] Error crítico: {str(e)}")
        return JsonResponse({
            "ok": False, 
            "error": str(e) if settings.DEBUG else "Error interno", 
            "reply": "Lo siento, ocurrió un error técnico inesperado."
        })
