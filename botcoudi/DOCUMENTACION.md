# Documentación Completa - BotCoudy - Módulo de IA Aislado

## 1. Descripción General del Proyecto

**Nombre del Proyecto:** BotCoudy  
**Propósito:** Sistema de gestión de proveedores de IA (OpenAI y Claude) con widget de chat interactivo y panel administrativo.  
**Stack Tecnológico:** Django 6.0+, PostgreSQL, Python 3.14, OpenAI API, Anthropic Claude API

### Objetivo Principal
Proporcionar un widget de chat en línea que se conecte automáticamente con múltiples proveedores de IA (OpenAI y Claude), con soporte para fallback automático cuando un proveedor falla, y un panel administrativo para gestionar configuraciones y prioridades.

---

## 2. Estructura del Proyecto

```
botcoudi/
├── botcoudi/                      # Proyecto Django principal
│   ├── settings.py               # Configuración de Django
│   ├── urls.py                   # Rutas principales
│   ├── wsgi.py                   # Configuración WSGI
│   └── ai/                        # Módulo de extractores de IA
│       ├── chat_extractor.py     # (Desactualizado, no se usa en widget)
│       ├── openAI/
│       │   └── extractor.py      # (Desactualizado, no se usa en widget)
│       └── Claude/
│           └── extractor.py      # (Desactualizado, no se usa en widget)
├── ai_manage/                     # App de gestión de proveedores y plantillas
│   ├── models.py                 # Modelos: AIProviderConfig, AIPromptTemplate
│   ├── admin.py                  # Panel administrativo de Django
│   ├── views.py                  # Vistas del dashboard
│   ├── forms.py                  # Formularios personalizados
│   ├── urls.py                   # Rutas de ai_manage
│   ├── migrations/               # Migraciones de base de datos
│   └── static/ai_manage/js/      # JS para admin (provider_model_filter.js)
├── widget/                        # App principal del widget de chat
│   ├── models.py                 # Modelos: WidgetConversation, WidgetMessage, AICallLog
│   ├── services.py               # Lógica de conexión con IA (CORE)
│   ├── views.py                  # API endpoint del widget
│   ├── urls.py                   # Rutas del widget
│   ├── migrations/               # Migraciones
│   └── admin.py                  # Admin del widget
├── templates/                     # Plantillas HTML
│   ├── dashboard.html            # Página de inicio
│   ├── widget/
│   │   └── prueba_widget.html    # Página de prueba del widget
│   └── ai_manage/
│       ├── configuracion.html    # (No se usa actualmente)
│       └── prompts.html          # (No se usa actualmente)
├── static/                        # Archivos estáticos
│   ├── css/
│   │   └── main.css              # Estilos CSS principales
│   ├── js/
│   │   └── widget.js             # Lógica del widget en frontend
│   └── ai_manage/js/
│       └── provider_model_filter.js # Placeholder para admin (vacío)
├── .env                          # Variables de entorno (NO VERSIONADO)
├── requirements.txt              # Dependencias de Python
├── manage.py                     # CLI de Django
└── DOCUMENTACION.md             # Este archivo

```

---

## 3. Cambios Realizados

### 3.1 Configuración de Django (botcoudi/settings.py)

**Cambios Clave:**

1. **Carga de Variables de Entorno (.env)**
   - Se agregó fallback manual para cargar `.env` si `python-dotenv` no está instalado.
   - `DJANGO_ENV` por defecto es `"local"` (habilita DEBUG automáticamente).
   - Todas las API Keys se leen desde `.env`, no están quemadas en código.

2. **Base de Datos**
   - Motor: `postgresql` (cambio de SQLite a PostgreSQL)
   - Variables desde `.env`:
     - `POSTGRES_DB` (default: "botcoudy")
     - `POSTGRES_USER` (default: "postgres")
     - `POSTGRES_PASSWORD`
     - `POSTGRES_HOST` (default: "localhost")
     - `POSTGRES_PORT` (default: "5432")

3. **Archivos Estáticos**
   - `STATIC_URL` = "/static/" (con slash inicial para servir en desarrollo)
   - `STATICFILES_DIRS` = [BASE_DIR / 'static']
   - `STATIC_ROOT` = BASE_DIR / 'staticfiles'

4. **Apps Instaladas**
   - `django.contrib.admin`
   - `django.contrib.auth`
   - `django.contrib.contenttypes`
   - `django.contrib.sessions`
   - `django.contrib.messages`
   - `django.contrib.staticfiles`
   - `ai_manage.apps.AiManageConfig` (gestión de proveedores)
   - `widget` (widget de chat)

5. **Configuración de IA**
   - `OPENAI_API_KEY` desde `.env`
   - `CLAUDE_API_KEY` desde `.env`
   - `OPENAI_MODEL` (default: "gpt-4o-mini")
   - `CLAUDE_MODEL` (default: "claude-haiku-4-5")

### 3.2 Rutas Principales (botcoudi/urls.py)

**Cambios Clave:**

1. Se agregó `staticfiles_urlpatterns()` para servir archivos CSS/JS en desarrollo.
2. Rutas configuradas:
   - `GET /` → Dashboard principal
   - `POST /widget/api/mensaje/` → Endpoint del widget para enviar mensajes
   - `GET /widget/prueba/` → Página de prueba del widget
   - `GET /admin/` → Panel administrativo de Django

### 3.3 Modelos de Base de Datos (ai_manage/models.py y widget/models.py)

#### AIProviderConfig (Gestión de Proveedores)
Tabla: `ai_manage_aiproviderconfig`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | ID autoincremental |
| provider | CharField(20, choices: "openai", "claude") | Proveedor de IA |
| model_name | CharField(100, choices) | Modelo específico (gpt-4o-mini, claude-haiku-4-5) |
| priority | PositiveInteger (default: 1) | Menor = mayor prioridad (orden de intento) |
| is_enabled | Boolean (default: True) | Si está activo |
| timeout_seconds | Decimal(6,2, default: 5) | Timeout en segundos (>0) |
| max_retries | PositiveInteger (default: 2) | Reintentos máximos |
| failure_policy | CharField(20, choices: "fallback") | Política al fallar |
| failure_threshold | PositiveInteger (default: 1) | Fallos antes de degradar |
| cooldown_seconds | Decimal(6,2, default: 0) | Espera antes de reintentar |
| created_at | DateTimeField | Fecha de creación |
| updated_at | DateTimeField | Última actualización |

**Validación:** Cada modelo debe corresponder con el proveedor. OpenAI solo con gpt-4o-mini, Claude solo con claude-haiku-4-5.

#### AIPromptTemplate (Plantillas de Prompts)
Tabla: `ai_manage_aiprompttemplate`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | ID autoincremental |
| name | CharField(255) | Nombre de la plantilla |
| use_case | CharField(100, choices) | Caso de uso (generic, chat_extraction, etc.) |
| description | TextField | Descripción |
| system_prompt | TextField | Prompt del sistema para la IA |
| user_prompt_template | TextField | Plantilla de prompt de usuario |
| is_active | Boolean (default: True) | Si está activa |
| created_at | DateTimeField | Fecha de creación |
| updated_at | DateTimeField | Última actualización |

**Campos Eliminados:** `provider`, `version` (simplificación solicitada)

#### WidgetConversation (Conversaciones del Widget)
Tabla: `widget_widgetconversation`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | ID autoincremental |
| session_id | CharField(255) | ID único de sesión del navegador |
| created_at | DateTimeField | Fecha de inicio |
| updated_at | DateTimeField | Última actualización |

#### WidgetMessage (Mensajes del Widget)
Tabla: `widget_widgetmessage`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | ID autoincremental |
| conversation | FK → WidgetConversation | Relación con conversación |
| role | CharField(20, choices: "user", "assistant") | Rol del mensaje |
| content | TextField | Contenido del mensaje |
| provider | CharField(50) | Proveedor que respondió (openai/claude) |
| model_name | CharField(100) | Modelo que respondió |
| metadata_json | JSONField | Datos adicionales (fallback, latencia, etc.) |
| created_at | DateTimeField | Fecha de creación |

#### AICallLog (Log de Llamadas a IA)
Tabla: `widget_aicalllog`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | PK | ID autoincremental |
| provider | CharField(50) | Proveedor usado (openai/claude) |
| model_name | CharField(100) | Modelo usado |
| status | CharField(20, choices: "success", "failed") | Estado de la llamada |
| request_json | JSONField | Datos enviados a la IA |
| response_json | JSONField | Respuesta recibida |
| error_message | TextField | Mensaje de error (si aplica) |
| latency_ms | PositiveInteger | Tiempo de respuesta en ms |
| created_at | DateTimeField | Fecha de creación |

---

## 4. Flujo de Funcionamiento

### 4.1 Envío de Mensaje desde el Widget (Frontend)

```javascript
// static/js/widget.js
POST /widget/api/mensaje/
{
  "message": "Hola, ¿en qué puedo ayudarte?"
}
```

### 4.2 Procesamiento en Backend (widget/views.py)

1. **Recepción:**
   - Valida que venga `message` en JSON.
   - Crea o recupera `WidgetConversation` por `session_id`.

2. **Guardado del Mensaje del Usuario:**
   - Crea `WidgetMessage` con `role="user"`, `content="Hola..."`

3. **Llamada a Servicio de IA:**
   - Invoca `get_ai_chat_response(messages)` de `widget/services.py`

4. **Respuesta:**
   - Retorna JSON con respuesta de la IA o error controlado.

### 4.3 Lógica de IA y Fallback (widget/services.py) - CORE

**Función:** `get_ai_chat_response(messages, use_case='generic')`

**Pasos:**

1. **Obtener Configuraciones Activas:**
   ```python
   configs = AIProviderConfig.objects.filter(is_enabled=True).order_by('priority', 'id')
   ```
   Respeta el orden de prioridad del panel admin.

2. **Obtener Plantilla de Prompt:**
   ```python
   prompt_template = AIPromptTemplate.objects.filter(use_case=use_case, is_active=True).first()
   system_prompt = prompt_template.system_prompt if prompt_template else "Eres un asistente de ayuda..."
   ```

3. **Construir Lista de Proveedores a Intentar:**
   - Si hay configs en DB: usa esas en orden de prioridad.
   - Si NO hay configs en DB: crea fallback desde `.env` (OpenAI primero).

4. **Loop de Intentos (Fallback):**
   ```python
   for provider_item in providers_to_try:
       try:
           if provider == 'openai':
               # Llamada a OpenAI con timeout y retries
               # Si falla: añade a failed_providers y continúa
           elif provider == 'claude':
               # Llamada a Claude con timeout y retries
               # Si falla: añade a failed_providers y continúa
       except Exception:
           # Log de error, guardado en AICallLog, continúa al siguiente
   ```

5. **Retorno JSON Normalizado:**

   **Si OpenAI responde (sin fallback):**
   ```json
   {
     "ok": true,
     "reply": "Texto de respuesta",
     "provider": "openai",
     "model": "gpt-4o-mini",
     "fallback_used": false,
     "failed_provider": null,
     "error": null
   }
   ```

   **Si OpenAI falla y Claude responde (con fallback):**
   ```json
   {
     "ok": true,
     "reply": "Texto de respuesta",
     "provider": "claude",
     "model": "claude-haiku-4-5",
     "fallback_used": true,
     "failed_provider": "openai",
     "error": null
   }
   ```

   **Si ambos fallan:**
   ```json
   {
     "ok": false,
     "reply": "No fue posible obtener respuesta de los proveedores de IA.",
     "provider": null,
     "model": null,
     "fallback_used": true,
     "failed_provider": "openai, claude",
     "error": "Todos los proveedores fallaron."
   }
   ```

### 4.4 Guardado en Base de Datos

1. **Cada llamada a IA se registra en `AICallLog`:**
   - Proveedor, modelo, estado (success/failed), request, response, latencia.

2. **Mensajes se guardan en `WidgetMessage`:**
   - Mensaje del usuario y respuesta de la IA con provider y modelo.

3. **Conversación se gestiona con `WidgetConversation`:**
   - Una sesión = una conversación.

---

## 5. Endpoints API

### 5.1 POST /widget/api/mensaje/

**Propósito:** Enviar un mensaje al chat y obtener respuesta de la IA.

**Request:**
```json
{
  "message": "Hola, ¿cuál es tu nombre?"
}
```

**Response (200 OK):**
```json
{
  "ok": true,
  "reply": "Me llamo BotCoudy...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "fallback_used": false,
  "failed_provider": null,
  "id": 123
}
```

**Response (200 OK con Error Controlado):**
```json
{
  "ok": false,
  "reply": "No fue posible obtener respuesta de los proveedores de IA.",
  "provider": null,
  "model": null,
  "error": "Todos los proveedores fallaron."
}
```

---

## 6. Panel Administrativo (Django Admin)

### 6.1 Gestión de Proveedores (AIProviderConfig)

**URL:** `http://127.0.0.1:8000/admin/ai_manage/aiproviderconfig/`

**Funcionalidades:**
- Agregar/editar proveedores (OpenAI, Claude).
- Establecer prioridad (menor = más prioritario).
- Configurar timeout (segundos).
- Configurar reintentos.
- Activar/desactivar proveedor.
- Ver última actualización.

**Validación Automática:**
- OpenAI solo puede usar modelo "gpt-4o-mini".
- Claude solo puede usar modelo "claude-haiku-4-5".

### 6.2 Gestión de Plantillas de Prompts (AIPromptTemplate)

**URL:** `http://127.0.0.1:8000/admin/ai_manage/aiprompttemplate/`

**Funcionalidades:**
- Crear/editar plantillas de prompts.
- Definir caso de uso (generic, chat_extraction, etc.).
- Escribir system_prompt (instrucciones del sistema).
- Escribir user_prompt_template (plantilla del usuario).
- Activar/desactivar plantilla.

**Nota:** Los campos `provider` y `version` fueron eliminados para simplificar el flujo.

### 6.3 Gestión del Widget (WidgetConversation, WidgetMessage, AICallLog)

**URLs:**
- `http://127.0.0.1:8000/admin/widget/widgetconversation/`
- `http://127.0.0.1:8000/admin/widget/widgetmessage/`
- `http://127.0.0.1:8000/admin/widget/aicalllog/`

**Funcionalidades:**
- Ver conversaciones activas.
- Ver historial de mensajes.
- Ver logs de llamadas a IA (para debugging).

---

## 7. Configuración de Variables de Entorno (.env)

**Ubicación:** `c:\Users\Bogarth\Documents\Proyectos\Proyecto coudibot 2\botcoudi\.env`

**Variables Requeridas:**

```env
# Django
DJANGO_ENV=local
DEBUG=True
DJANGO_SECRET_KEY=django-insecure-...

# PostgreSQL
POSTGRES_DB=botcoudy
POSTGRES_USER=postgres
POSTGRES_PASSWORD=Postgre2026@%
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Claude (Anthropic)
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-haiku-4-5

# Timeouts y Reintentos (opcionales, se configuran en admin también)
OPENAI_TIMEOUT=10.0
CLAUDE_TIMEOUT=10.0
OPENAI_MAX_RETRIES=2
CLAUDE_MAX_RETRIES=2
```

**Notas:**
- Las API Keys **NO deben estar en código** ni en git.
- `.env` está en `.gitignore`.
- Si `DJANGO_ENV=local`, Django automáticamente habilita `DEBUG=True`.

---

## 8. Instrucciones de Instalación y Configuración

### 8.1 Requisitos Previos

- Python 3.14+
- PostgreSQL 12+ (instalado y corriendo en localhost:5432)
- pip (gestor de paquetes de Python)

### 8.2 Pasos de Instalación

#### 1. Clonar/Descargar el Proyecto
```bash
cd "c:\Users\Bogarth\Documents\Proyectos\Proyecto coudibot 2\botcoudi"
```

#### 2. Crear Archivo .env
```bash
# Copiar plantilla o crear manualmente con los valores de la sección 7
```

#### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

**Dependencias Principales:**
- `django==6.0.5`
- `psycopg2-binary` (driver de PostgreSQL)
- `openai` (librería de OpenAI)
- `anthropic` (librería de Claude)
- `python-dotenv` (opcional, para cargar .env)

#### 4. Crear Base de Datos en PostgreSQL
```sql
CREATE DATABASE botcoudy OWNER postgres;
```

#### 5. Ejecutar Migraciones
```bash
python manage.py migrate
```

Esto crea las tablas en PostgreSQL.

#### 6. Crear Superusuario (Admin)
```bash
python manage.py createsuperuser
```

Sigue los pasos para crear usuario y contraseña.

#### 7. Ejecutar Servidor de Desarrollo
```bash
python manage.py runserver
```

Accesible en `http://127.0.0.1:8000/`

---

## 9. Acceso a Interfaces

### 9.1 Dashboard Principal
- **URL:** `http://127.0.0.1:8000/`
- **Descripción:** Página de bienvenida con enlaces a todas las funciones.

### 9.2 Widget de Prueba
- **URL:** `http://127.0.0.1:8000/widget/prueba/`
- **Descripción:** Interfaz de chat para probar el widget en tiempo real.
- **Funcionalidad:** Envía mensajes y recibe respuestas de OpenAI o Claude con fallback automático.

### 9.3 Panel Administrativo
- **URL:** `http://127.0.0.1:8000/admin/`
- **Credenciales:** Usuario y contraseña creados en `createsuperuser`
- **Funcionalidad:** Gestionar proveedores, plantillas, mensajes y logs.

---

## 10. Migraciones de Base de Datos

### 10.1 Crear Migraciones Después de Cambios en Modelos

```bash
python manage.py makemigrations ai_manage
python manage.py makemigrations widget
```

### 10.2 Aplicar Migraciones

```bash
python manage.py migrate
```

### 10.3 Verificar Estado de Migraciones

```bash
python manage.py showmigrations
```

---

## 11. Troubleshooting

### Problema: "no existe la relación widget_widgetconversation"

**Causa:** Las migraciones no fueron ejecutadas.

**Solución:**
```bash
python manage.py migrate
```

### Problema: "Request timed out" o "Connection refused"

**Causas Posibles:**
1. Las API Keys no están configuradas en `.env`.
2. El timeout es muy bajo en el panel admin (aumentar a 10-20s).
3. La conexión a internet está lenta.

**Solución:**
1. Verificar `.env`:
   ```bash
   echo %OPENAI_API_KEY%
   echo %CLAUDE_API_KEY%
   ```
2. En admin, editar configuración del proveedor y aumentar `timeout_seconds`.

### Problema: PostgreSQL no se conecta

**Causa:** Credenciales incorrectas o PostgreSQL no corriendo.

**Solución:**
```bash
# Verificar que PostgreSQL está corriendo
# Windows: Services → PostgreSQL
# Linux: sudo systemctl status postgresql

# Verificar credenciales en .env
# Conectar manualmente con psql:
psql -h localhost -U postgres -d botcoudy
```

### Problema: CSS no carga (solo texto en la página)

**Causa:** `STATIC_URL` mal configurado o `staticfiles_urlpatterns()` no agregado.

**Solución:**
1. Verificar `botcoudi/settings.py`: `STATIC_URL = "/static/"`
2. Verificar `botcoudi/urls.py`: contiene `urlpatterns += staticfiles_urlpatterns()`
3. Recargar página con `Ctrl+F5`

### Problema: "ModuleNotFoundError: No module named 'openai'"

**Causa:** Librería `openai` no instalada.

**Solución:**
```bash
pip install openai anthropic
```

### Problema: El widget responde siempre con "Fallback activo" o "no hay proveedores"

**Causa:** Configuración de proveedores no está activa.

**Solución:**
1. Ir a `http://127.0.0.1:8000/admin/ai_manage/aiproviderconfig/`
2. Verificar que ambos proveedores están "Activos" (checkbox marcado).
3. Establecer prioridades: OpenAI = 1, Claude = 2 (1 = más prioritario).
4. Verificar API Keys en `.env` están correctas.
5. Aumentar `timeout_seconds` si da timeouts frecuentes.

---

## 12. Changelog de Cambios Realizados

### Fase 1: Configuración Base
- ✅ Creación de apps `ai_manage` y `widget`.
- ✅ Configuración de PostgreSQL en settings.py.
- ✅ Carga segura de variables de entorno desde .env.

### Fase 2: Modelos de Base de Datos
- ✅ Creación de modelos: AIProviderConfig, AIPromptTemplate, WidgetConversation, WidgetMessage, AICallLog.
- ✅ Validación de que modelos corresponden con proveedores.
- ✅ Migraciones iniciales.

### Fase 3: Panel Administrativo
- ✅ Setup de Django Admin para AIProviderConfig.
- ✅ Setup de Django Admin para AIPromptTemplate.
- ✅ Formulario personalizado para validar provider ↔ model.

### Fase 4: Widget y Servicios de IA
- ✅ Creación de endpoint POST `/widget/api/mensaje/`.
- ✅ Implementación de lógica de fallback en `widget/services.py`.
- ✅ Conexión con OpenAI (librería `openai`).
- ✅ Conexión con Claude (librería `anthropic`).
- ✅ Guardado de logs en AICallLog.

### Fase 5: Frontend del Widget
- ✅ Creación de página de prueba del widget.
- ✅ Script JavaScript para enviar mensajes.
- ✅ Visualización de respuestas con info de proveedor.

### Fase 6: Correcciones de Estática y Rutas
- ✅ Fix: CSS no cargaba → corrección de STATIC_URL a "/static/".
- ✅ Fix: Agregación de `staticfiles_urlpatterns()` en urls.py.
- ✅ Fix: Agregación de archivo placeholder `provider_model_filter.js` para admin.

### Fase 7: Priorización y Fallback
- ✅ Implementación de orden respetando prioridad del panel admin.
- ✅ Garantía de que cualquier proveedor habilitado funciona como principal.
- ✅ Fallback automático al siguiente si falla el primero.

### Fase 8: Simplificación de Plantillas
- ✅ Eliminación de campos `provider` y `version` en AIPromptTemplate.
- ✅ Actualización de admin.py para reflejar cambios.
- ✅ Validación de que el flujo sigue funcionando sin esos campos.

---

## 13. Referencia Rápida de Comandos

```bash
# Iniciar servidor
python manage.py runserver

# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Ver estado de migraciones
python manage.py showmigrations

# Shell interactivo
python manage.py shell

# Limpiar datos de prueba
python manage.py flush

# Acceder a admin
# URL: http://127.0.0.1:8000/admin/
```

---

## 14. Conclusión y Notas Finales

Este proyecto proporciona una solución robusta para integrar múltiples proveedores de IA con fallback automático. La arquitectura permite:

1. **Flexibilidad:** Cambiar prioridades de proveedores desde el panel admin sin tocar código.
2. **Confiabilidad:** Si OpenAI falla, Claude responde automáticamente.
3. **Trazabilidad:** Todos los intentos de IA se registran en AICallLog.
4. **Escalabilidad:** Fácil agregar nuevos proveedores de IA.

Para cualquier duda o contribución, revisar el código en los archivos mencionados arriba.

---

**Versión de Documentación:** 1.0  
**Fecha de Última Actualización:** 2026-05-22  
**Mantenido por:** Equipo de Desarrollo BotCoudy
