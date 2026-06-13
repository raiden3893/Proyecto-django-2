import logging
import time
import json
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from ai_manage.models import AIProviderConfig, AIPromptTemplate
from .models import AICallLog # Importar AICallLog desde el mismo directorio
from .Prompt_manager import PromptManager # Importar PromptManager desde el mismo directorio
# Intentar importar las librerías necesarias
try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger(__name__)
    
def _save_call_log(provider, model, status, request_data, response_data, error=None, latency=0):
    """
    Guarda el log de la llamada en la base de datos.
    """
    try:
        AICallLog.objects.create(
            provider=provider,
            model_name=model,
            status=status,
            request_json=request_data,
            response_json=response_data if isinstance(response_data, dict) else {"raw": str(response_data)},
            error_message=str(error) if error else None,
            latency_ms=int(latency)
        )
    except Exception as e:
        logger.error(f"Error guardando AICallLog: {str(e)}")

def get_ai_chat_response(
    messages,
    use_case='generic',
    system_prompt_override=None,
    temperature=0.0,
    response_schema=None,
    response_validator=None,
):
    """
    Obtiene una respuesta de la IA con fallback y persistencia.
    Optimizado para devolver JSON estructurado.
    """
    
    configs = []
    
    default_system = "Eres un asistente para BotCoudy. Responde de forma amable."
    
    try:
        configs = list(AIProviderConfig.objects.filter(is_enabled=True).order_by('priority', 'id'))
        system_prompt = PromptManager.resolve_system_prompt(use_case, default_system)
    except Exception as error:
        logger.warning("[AI_MANAGER] Error cargando config/prompts: %s", error)
        system_prompt = default_system

    if system_prompt_override:
        if system_prompt:
            system_prompt = f"{system_prompt}\n\n{system_prompt_override}".strip()
        else:
            system_prompt = system_prompt_override
        logger.info("[AI_MANAGER] Usando prompt proporcionado por el código (override).")

    # 3. Determinar proveedores a intentar
    if not configs:
        logger.warning("[AI_MANAGER] No hay proveedores habilitados en DB. Usando configuración de entorno.")
        providers_to_try = []
        if settings.OPENAI_API_KEY:
            providers_to_try.append({'provider': 'openai', 'model': settings.OPENAI_MODEL})
        if settings.CLAUDE_API_KEY:
            providers_to_try.append({'provider': 'claude', 'model': settings.CLAUDE_MODEL})
    else:
        providers_to_try = [{'provider': c.provider, 'model': c.model_name, 'config': c} for c in configs]

    if not providers_to_try:
        logger.error("[AI_MANAGER] Error: No hay proveedores de IA configurados.")
        return {
            "ok": False,
            "reply": "No hay proveedores de IA configurados y activos.",
            "error": "No providers available"
        }

    provider_list_str = ", ".join([
        f"{p['provider']}:{p['model']} (prioridad={getattr(p.get('config'), 'priority', 'env')})"
        for p in providers_to_try
    ])
    logger.info("[AI_MANAGER] Proveedores activos encontrados: %s", provider_list_str)

    # La prioridad del Admin es la unica fuente de verdad.
    # No reordenamos por historial de conversación para evitar que un proveedor previo
    # anule el orden configurado en la base de datos.
    last_user_msg = ""
    if messages:
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = str(m.get("content", "")).lower()
                break

    logger.info(
        "[AI_MANAGER] Orden efectivo tras DB: %s",
        [f"{item['provider']}:{item['model']}" for item in providers_to_try],
    )

    failed_providers = []

    # Sanitizar mensajes para las APIs (quitar campos extra como 'provider')
    clean_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    for index, item in enumerate(providers_to_try):
        provider = item['provider']
        model = item['model']
        config = item.get('config')
        
        logger.info("[AI_MANAGER] Intentando proveedor: %s usando modelo: %s", provider, model)
        start_time = time.time()
        
        try:
            if provider == 'openai':
                if not openai:
                    raise Exception("Librería openai no disponible")
                
                api_key = settings.OPENAI_API_KEY
                if not api_key:
                    raise Exception("OPENAI_API_KEY no configurada")
                
                # Widget optimization: try each provider only once
                timeout = float(config.timeout_seconds) if config else 5.0
                retries = 0 

                # TEST: Disparador de fallo manual para verificar fallback
                # Solo falla si el ÚLTIMO mensaje enviado por el usuario contiene "fallar"
                if "fallar" in last_user_msg:
                    # REGLA DE PRUEBA: Solo fallamos si este proveedor es el de mayor prioridad configurada
                    # o si es el primero en este intento específico.
                    primary_provider = providers_to_try[0]['provider']
                    if provider == primary_provider:
                        logger.warning("[TEST] Simulando fallo crítico del proveedor primario (%s) por trigger 'fallar'", provider)
                        raise Exception(f"Error de conexión simulado en {provider} (Trigger detectado)")
                
                client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=retries)
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": system_prompt}] + clean_messages,
                        temperature=temperature,
                        response_format={"type": "json_object"} if "gpt-4" in model or "gpt-3.5-turbo-0125" in model else None
                    )
                except TypeError as error:
                    # Fallback si el SDK no soporta response_format.
                    logger.warning("[AI_MANAGER] response_format no soportado, reintentando sin él: %s", error)
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": system_prompt}] + clean_messages,
                        temperature=temperature,
                    )
                reply = response.choices[0].message.content
                logger.info("[AI_MANAGER] Respuesta cruda recibida de %s: longitud=%d", provider, len(reply or ""))
                raw_resp = response.model_dump()
                
            elif provider == 'claude':
                if not anthropic:
                    raise Exception("Librería anthropic no disponible")
                
                api_key = settings.CLAUDE_API_KEY
                if not api_key:
                    raise Exception("CLAUDE_API_KEY no configurada")
                
                # Widget optimization: try each provider only once
                timeout = float(config.timeout_seconds) if config else 5.0
                retries = 0
                
                client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=retries)
                
                # TEST: Disparador de fallo manual para Claude
                if "fallar" in last_user_msg:
                    primary_provider = providers_to_try[0]['provider']
                    if provider == primary_provider:
                        logger.warning("[TEST] Simulando fallo crítico del proveedor primario (%s) por trigger 'fallar'", provider)
                        raise Exception(f"Error de conexión simulado en {provider} (Trigger detectado)")

                claude_kwargs = {
                    "model": model,
                    "max_tokens": 2048,
                    "system": system_prompt,
                    "messages": clean_messages,
                    "temperature": temperature,
                }
                if response_schema:
                    # Intento de JSON mode para Claude (si el SDK/Modelo lo soporta)
                    try:
                        claude_kwargs["output_config"] = {
                            "format": {
                                "type": "json_schema",
                                "schema": response_schema,
                            }
                        }
                        response = client.messages.create(**claude_kwargs)
                    except Exception as e:
                        logger.warning("[AI_MANAGER] Falló output_config en Claude, reintentando sin él: %s", e)
                        claude_kwargs.pop("output_config", None)
                        response = client.messages.create(**claude_kwargs)
                else:
                    response = client.messages.create(**claude_kwargs)
                
                reply = response.content[0].text
                logger.info("[AI_MANAGER] Respuesta cruda recibida de %s: longitud=%d", provider, len(reply or ""))
                raw_resp = {
                    "id": response.id,
                    "model": response.model,
                    "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
                }
            else:
                logger.warning("[AI_MANAGER] Proveedor no soportado: %s", provider)
                continue

            if response_validator:
                try:
                    is_valid = response_validator(reply)
                except Exception as error:
                    raise Exception(f"Validador de respuesta falló: {error}") from error
                if not is_valid:
                    logger.warning("[AI_MANAGER] Falló %s: Respuesta inválida según el validador", provider)
                    raise Exception("Respuesta no cumple el esquema")

            latency = (time.time() - start_time) * 1000
            _save_call_log(provider, model, 'success', {"system": system_prompt, "messages": messages}, raw_resp, latency=latency)
            
            logger.info("[AI_MANAGER] Respuesta recibida y validada correctamente de %s", provider)
            return {
                "ok": True,
                "reply": reply,
                "provider": provider,
                "model": model,
                "provider_label": provider.upper(),
                "model_name": model,
                "fallback_used": len(failed_providers) > 0,
                "failed_provider": failed_providers[-1] if failed_providers else None,
                "failed_providers": failed_providers
            }

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            error_msg = str(e)
            logger.error("[AI_MANAGER] Falló %s: %s", provider, error_msg)
            _save_call_log(provider, model, 'failed', {"system": system_prompt, "messages": messages}, None, error=error_msg, latency=latency)
            failed_providers.append(provider)
            if index + 1 < len(providers_to_try):
                next_provider = providers_to_try[index + 1].get("provider")
                logger.warning("[AI_MANAGER] Intentando fallback con %s", next_provider)
            continue

    return {
        "ok": False,
        "reply": "Lo siento, por el momento no fue posible procesar tu mensaje con los proveedores de IA configurados.",
        "error": "All providers failed",
        "failed_provider": failed_providers[-1] if failed_providers else None,
        "failed_providers": failed_providers
    }
