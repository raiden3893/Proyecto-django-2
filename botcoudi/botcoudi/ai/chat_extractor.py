import logging
import os

from django.conf import settings

from botcoudi.ai.openAI.extractor import extraer_datos_via_openai
from botcoudi.ai.Claude.extractor import extraer_datos_via_claude


logger = logging.getLogger(__name__)


def _get_db_provider_configs():
    try:
        from ai_manage.models import AIProviderConfig
    except Exception as error:
        logger.warning("AI config DB no disponible: %s", error)
        return []

    try:
        return list(AIProviderConfig.objects.filter(is_enabled=True).order_by("priority"))
    except Exception as error:
        logger.warning("AI config DB error: %s", error)
        return []


def _normalize_provider(name: str) -> str:
    value = (name or "").strip().lower()
    if value in {"chatgpt", "openai"}:
        return "openai"
    if value == "claude":
        return "claude"
    return "openai"


def _get_model_for(provider: str) -> str | None:
    if provider == "openai":
        model = getattr(settings, "OPENAI_MODEL", None) or os.getenv("OPENAI_MODEL")
        if model:
            return model
        if _normalize_provider(getattr(settings, "AI_CHAT_EXTRACTOR", "")) == "openai":
            return getattr(settings, "AI_CHAT_EXTRACTOR_MODEL", None)
        return None

    if provider == "claude":
        model = (
            getattr(settings, "CLAUDE_MODEL", None)
            or getattr(settings, "ANTHROPIC_MODEL", None)
            or os.getenv("CLAUDE_MODEL")
            or os.getenv("ANTHROPIC_MODEL")
        )
        if model:
            return model
        if _normalize_provider(getattr(settings, "AI_CHAT_EXTRACTOR", "")) == "claude":
            return getattr(settings, "AI_CHAT_EXTRACTOR_MODEL", None)
        return None

    return None


def _log_fallback_message(failed_provider: str, failed_model: str | None, next_provider: str, next_model: str | None) -> None:
    if not failed_model or not next_model:
        return

    if failed_provider == "openai" and next_provider == "claude":
        logger.warning(
            "OpenAI %s dejo de funcionar, se cambio la IA a Claude %s",
            failed_model,
            next_model,
        )
        return

    if failed_provider == "claude" and next_provider == "openai":
        logger.warning(
            "Claude %s dejo de funcionar, se cambio la IA a OpenAI %s",
            failed_model,
            next_model,
        )
        return


def extraer_datos_via_ai(historial_texto, idioma="es"):
    db_configs = _get_db_provider_configs()
    if db_configs:
        for index, config in enumerate(db_configs):
            provider = config.provider
            model = config.model_name
            timeout_seconds = config.timeout_seconds
            max_retries = config.max_retries
            failure_policy = getattr(config, "failure_policy", "fallback")

            if provider not in {"openai", "claude"}:
                logger.warning("AI extractor proveedor no soportado: %s", provider)
                continue

            try:
                if provider == "openai":
                    api_key = getattr(settings, "OPENAI_API_KEY", None)
                    if not api_key:
                        logger.warning("Fallback: OPENAI_API_KEY no configurada")
                        logger.warning("OPENAI_API_KEY no configurada")
                        if failure_policy == "stop":
                            break
                        continue

                    data = extraer_datos_via_openai(
                        historial_texto,
                        api_key,
                        idioma=idioma,
                        model=model,
                        raise_on_error=True,
                        timeout_seconds=timeout_seconds,
                        max_retries=max_retries,
                    )
                else:
                    api_key = (
                        getattr(settings, "CLAUDE_API_KEY", None)
                        or getattr(settings, "ANTHROPIC_API_KEY", None)
                    )
                    if not api_key:
                        logger.warning("Fallback: CLAUDE_API_KEY no configurada")
                        logger.warning("CLAUDE_API_KEY no configurada")
                        if failure_policy == "stop":
                            break
                        continue

                    data = extraer_datos_via_claude(
                        historial_texto,
                        api_key,
                        idioma=idioma,
                        model=model,
                        raise_on_error=True,
                        timeout_seconds=timeout_seconds,
                        max_retries=max_retries,
                    )

                if data:
                    return data

                logger.warning(
                    "AI extractor devolvio respuesta vacia (%s). Fallback en curso.",
                    provider,
                )
                if failure_policy == "stop":
                    break
                continue

            except Exception as error:
                next_provider = None
                next_model = None
                if index + 1 < len(db_configs):
                    next_provider = db_configs[index + 1].provider
                    next_model = db_configs[index + 1].model_name
                else:
                    next_provider = "claude" if provider == "openai" else "openai"
                    next_model = _get_model_for(next_provider)

                _log_fallback_message(provider, model, next_provider, next_model)
                logger.warning("Fallback por error de API (%s): %s", provider, error)
                logger.warning("AI extractor fallo (%s). Fallback en curso. Detalle: %s", provider, error)
                if failure_policy == "stop":
                    break
                continue

        return {}

    primary = _normalize_provider(getattr(settings, "AI_CHAT_EXTRACTOR", ""))
    order = [primary, "claude" if primary == "openai" else "openai"]

    for provider in order:
        model = _get_model_for(provider)
        if not model:
            logger.warning("AI extractor sin modelo para proveedor %s", provider)
            continue

        try:
            if provider == "openai":
                api_key = getattr(settings, "OPENAI_API_KEY", None)
                if not api_key:
                    logger.warning("Fallback: OPENAI_API_KEY no configurada")
                    logger.warning("OPENAI_API_KEY no configurada")
                    continue

                data = extraer_datos_via_openai(
                    historial_texto,
                    api_key,
                    idioma=idioma,
                    model=model,
                    raise_on_error=True,
                )
            else:
                api_key = (
                    getattr(settings, "CLAUDE_API_KEY", None)
                    or getattr(settings, "ANTHROPIC_API_KEY", None)
                )
                if not api_key:
                    logger.warning("Fallback: CLAUDE_API_KEY no configurada")
                    logger.warning("CLAUDE_API_KEY no configurada")
                    continue

                data = extraer_datos_via_claude(
                    historial_texto,
                    api_key,
                    idioma=idioma,
                    model=model,
                    raise_on_error=True,
                )

            if data:
                return data

            logger.warning(
                "AI extractor devolvio respuesta vacia (%s). Fallback en curso.",
                provider,
            )
            continue

        except Exception as error:
            next_provider = "claude" if provider == "openai" else "openai"
            next_model = _get_model_for(next_provider)
            _log_fallback_message(provider, model, next_provider, next_model)
            logger.warning("Fallback por error de API (%s): %s", provider, error)
            logger.warning("AI extractor fallo (%s). Fallback en curso. Detalle: %s", provider, error)
            continue

    return {}
