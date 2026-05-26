/**
 * Widget de chat de BotCoudy.
 *
 * Funcionalidades:
 * - Envío de mensajes al endpoint /widget/api/mensaje/ vía POST.
 * - Visualización de respuestas del bot con información del proveedor.
 * - Actualización dinámica del panel de "Datos del Lead" con los datos
 *   capturados en tiempo real.
 * - Indicador de fallback y proveedor de IA.
 * - Soporte para el comando REINICIAR.
 */

document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const statusText = document.getElementById('connection-status');

    /**
     * Gestión del session_id persistente.
     */
    const getSessionId = () => {
        let sid = localStorage.getItem('botcoudy_session_id');
        if (!sid) {
            sid = 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
            localStorage.setItem('botcoudy_session_id', sid);
        }
        return sid;
    };

    const resetSessionId = () => {
        localStorage.removeItem('botcoudy_session_id');
        return getSessionId();
    };

    let currentSessionId = getSessionId();

    // Elementos del panel de lead.
    const leadFields = {
        nombre: {
            value: document.getElementById('val-nombre'),
            icon: document.getElementById('icon-nombre'),
        },
        telefono: {
            value: document.getElementById('val-telefono'),
            icon: document.getElementById('icon-telefono'),
        },
        email: {
            value: document.getElementById('val-email'),
            icon: document.getElementById('icon-email'),
        },
        disponibilidad: {
            value: document.getElementById('val-disponibilidad'),
            icon: document.getElementById('icon-disponibilidad'),
        },
    };
    const statusBadge = document.getElementById('lead-status-badge');
    const stepLabel = document.getElementById('lead-step-label');

    /**
     * Agrega un mensaje a la interfaz de chat.
     * @param {string} text - Contenido del mensaje.
     * @param {string} sender - 'user' o 'bot'.
     * @param {object} info - Información extra (provider, fallback, etc).
     */
    const addMessage = (text, sender, info = null) => {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(sender === 'user' ? 'user-message' : 'bot-message');

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');
        contentDiv.textContent = text;
        messageDiv.appendChild(contentDiv);

        // Mostrar información del proveedor en respuestas del bot.
        const providerRaw = String((info && (info.provider || info.provider_label)) || '').trim();
        const modelRaw = String((info && (info.model || info.model_name)) || '').trim();
        if (sender === 'bot' && (providerRaw || modelRaw)) {
            const infoDiv = document.createElement('div');
            infoDiv.className = 'message-info';
            
            const providerName = providerRaw ? providerRaw.toUpperCase() : 'IA';
            infoDiv.textContent = modelRaw ? `${providerName} - ${modelRaw}` : providerName;
            
            messageDiv.appendChild(infoDiv);
        }

        chatMessages.appendChild(messageDiv);
        // Auto-scroll al final.
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    /**
     * Actualiza el panel lateral de datos del lead.
     * @param {object} leadData - Datos del lead (nombre, telefono, email, disponibilidad).
     */
    const updateLeadPanel = (leadData) => {
        if (!leadData) return;
        console.log("[Widget] lead_data recibido:", leadData);

        // Actualizar cada campo del panel.
        const fieldNames = ['nombre', 'telefono', 'email', 'disponibilidad'];
        fieldNames.forEach(field => {
            const el = leadFields[field];
            if (!el || !el.value || !el.icon) return;

            const value = leadData[field];

            if (value && value.trim() !== '') {
                // Campo capturado: mostrar valor y marcar como completado.
                el.value.textContent = value;
                el.value.classList.remove('empty');
                el.icon.classList.remove('pending');
                el.icon.classList.add('captured');
            } else {
                // Campo pendiente.
                el.value.textContent = 'Pendiente';
                el.value.classList.add('empty');
                el.icon.classList.remove('captured');
                el.icon.classList.add('pending');
            }
        });
    };
    
    const updateLeadStatus = (leadState) => {
        if (!leadState) return;
        
        // Actualizar badge de estado.
        if (statusBadge) {
            const isComplete = leadState.is_complete;
            statusBadge.classList.remove('in-progress', 'completed', 'abandoned');
            if (isComplete) {
                statusBadge.classList.add('completed');
                statusBadge.innerHTML = '✅ Completado';
            } else {
                statusBadge.classList.add('in-progress');
                statusBadge.innerHTML = '⏳ En progreso';
            }
        }

        // Actualizar label del paso actual.
        if (stepLabel) {
            const step = leadState.current_block || leadState.current_step || 'inicio';
            const stepNames = {
                'greeting': 'Saludo',
                'name': 'Nombre',
                'phone': 'Teléfono',
                'email': 'Email',
                'insist': 'Insistir',
                'availability': 'Disponibilidad',
                'closing': 'Cierre',
                'custom': 'Personalizado',
                'contextual': 'Contextual',
                'menu': 'Menú',
                'completed': 'Completado',
                'completado': 'Completado',
                'no_aplica': 'Sin paso',
                'nombre': 'Nombre',
                'telefono': 'Teléfono',
                'disponibilidad': 'Disponibilidad',
            };
            stepLabel.textContent = `Paso: ${stepNames[step] || step}`;
        }
    };

    /**
     * Resetea el panel de lead a su estado inicial.
     */
    const resetLeadPanel = () => {
        updateLeadPanel({
            nombre: '',
            telefono: '',
            email: '',
            disponibilidad: '',
            is_complete: false,
            current_step: 'nombre'
        });
    };

    /**
     * Manejador del envío del formulario.
     */
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const message = userInput.value.trim();
        if (!message) return;

        // Mostrar mensaje del usuario.
        addMessage(message, 'user');
        userInput.value = '';
        statusText.textContent = 'Pensando...';

        // Deshabilitar botón de envío mientras procesa.
        const sendBtn = document.getElementById('send-btn');
        if (sendBtn) sendBtn.disabled = true;

        try {
            console.log("[Widget] Enviando mensaje con session_id:", currentSessionId);
            // Enviar mensaje al backend.
            const response = await fetch('/widget/api/mensaje/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: message,
                    session_id: currentSessionId
                })
            });

            const data = await response.json();

            if (data.ok) {
                // Si el backend nos dio un nuevo session_id (por reset o completado)
                if (data.conversation_id && data.conversation_id !== currentSessionId) {
                    console.log("[Widget] Nueva sesión recibida:", data.conversation_id);
                    currentSessionId = data.conversation_id;
                    localStorage.setItem('botcoudy_session_id', currentSessionId);
                }

                // Mostrar respuesta del bot con info del proveedor.
                setTimeout(() => {
                    addMessage(data.reply, 'bot', {
                        provider: data.provider,
                        model: data.model,
                        provider_label: data.provider_label,
                        provider_source: data.provider_source,
                        fallback_used: data.fallback_used
                    });
                    
                    if (data.lead_saved) {
                        statusText.textContent = 'Lead guardado correctamente';
                    } else {
                        statusText.textContent = 'Listo';
                    }
                }, 300);

                // Actualizar panel de datos y estado.
                updateLeadPanel(data.lead_data || data.lead_state);
                updateLeadStatus(data.lead_state);

                // Si fue un reinicio manual, limpiar panel visual.
                if (message.trim().toUpperCase() === 'REINICIAR') {
                    resetLeadPanel();
                }
            } else {
                addMessage(data.reply || ('Error: ' + (data.error || 'Ocurrió un problema.')), 'bot', {
                    provider_source: 'error'
                });
                statusText.textContent = 'Error';
            }
        } catch (error) {
            console.error('Error al enviar el mensaje:', error);
            addMessage('Error de red. Asegúrate de que el servidor esté corriendo.', 'bot');
            statusText.textContent = 'Error de red';
        } finally {
            // Rehabilitar botón de envío.
            if (sendBtn) sendBtn.disabled = false;
            userInput.focus();
        }
    });
});
