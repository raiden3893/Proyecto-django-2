import logging
from django.core.cache import cache
from ai_manage.models import AIPromptTemplate

logger = logging.getLogger(__name__)

class PromptManager:
    #Este bloque funcionara como el inspector para ver si el prompt esta en la canche de django 
    #Se pretende que el canche y el prompt se mantenga en la memoria por 5 minutos para evitar exceso de memoria en el sistema

    @staticmethod
    def get_active_template(use_case: str):
        cache_key = f"prompt_template_{use_case}"
        data = cache.get(cache_key)
        
        if data is None:
            try:
                # Si no está en caché, lo buscamos en la base de datos
                template = AIPromptTemplate.objects.filter(
                    use_case=use_case, 
                    is_active=True
                ).order_by("-updated_at").first()

                if template:
                    data = {
                        "system_prompt": template.system_prompt,
                        "user_prompt_template": template.user_prompt_template,
                    }
                    
                    cache.set(cache_key, data, 300)
            except Exception as e:
                logger.error(f"[PromptManager] Error al consultar DB para {use_case}: {e}")
        
        return data
    @classmethod
    def resolve_system_prompt(cls, use_case: str, default: str) -> str:
        """Retorna el prompt de sistema configurado o un respaldo (default)."""
        template = cls.get_active_template(use_case)
        if template and template.get("system_prompt"):
            return template["system_prompt"].strip()
        return default

    @classmethod
    def resolve_user_prompt(cls, use_case: str, context: dict, default: str) -> str:
        """Formatea la plantilla de usuario con variables dinámicas."""
        template_data = cls.get_active_template(use_case)
        template_str = template_data.get("user_prompt_template") if template_data else default
        
        if not template_str:
            return default

        
        formatted = template_str
        for key, value in context.items():
            formatted = formatted.replace(f"{{{key}}}", str(value))
        return formatted
                
