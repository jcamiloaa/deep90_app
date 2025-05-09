# JSON de ejemplo para el flujo de configuración de personalidad del asistente
import os
import json
from django.conf import settings

# Los data-source se inyectarán dinámicamente desde la vista
ASSISTANT_CONFIG_FLOW_JSON = {
    "version": "7.0",
    "data_api_version": "3.0",
    "routing_model": {
        "WELCOME": ["CONFIG_PERSONALITY"],
        "CONFIG_PERSONALITY": ["CONFIG_PREFERENCES"],
        "CONFIG_PREFERENCES": []
    },
    "screens": [
        {
            "id": "WELCOME",
            "title": "Configura tu Asistente de Fútbol",
            "data": {
                "welcome_text": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "__example__": [
                        "🌟 *Personaliza tu experiencia:*\n\n• 🤖 **Nombre único** - ¡Crea su identidad!\n• 🎙️ **Estilo** - Técnico o coloquial\n• 📈 **Nivel de análisis** - Básico a Profundo",
                        "✅ *Beneficios clave:*\n▸ Predicciones con tu sello personal 🎯\n▸ Datos en tiempo real de tus equipos ⏱️\n▸ Explicación de cuotas 🔔\n",
                        "👇 *¡Vamos a configurar tu ANALISTA IDEAL!*"
                    ]
                }
            },
            "layout": {
                "type": "SingleColumnLayout",
                "children": [
                    {
                        "type": "Image",
                        "src": "iVBORw0KGgoAAAANSUhEUgAABAAAAAQACAYAAAB",
                        "height": 60,
                        "scale-type": "cover"
                    },
                    {
                        "type": "TextBody",
                        "markdown": True,
                        "text": "${data.welcome_text}"
                    },
                    {
                        "type": "Footer",
                        "label": "Personalizar",
                        "on-click-action": {
                            "name": "data_exchange",
                            "payload": {}
                        }
                    }
                ]
            }
        },
        {
            "id": "CONFIG_PERSONALITY",
            "title": "Personalidad del Asistente",
            "data": {
                "language_styles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"}
                        }
                    },
                    "__example__": [
                        {"id": "normal", "title": "Lenguaje sencillo"},
                        {"id": "tecnico", "title": "Técnico y analítico T"}
                    ]
                },
                "experience_levels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"}
                        }
                    },
                    "__example__": [
                        {"id": "baja", "title": "Principiante"},
                        {"id": "media", "title": "Intermedio"},
                        {"id": "alta", "title": "Avanzado"}
                    ]
                }
            },
            "layout": {
                "type": "SingleColumnLayout",
                "children": [
                    {
                        "type": "Form",
                        "name": "personality_form",
                        "children": [
                            {
                                "type": "TextSubheading",
                                "text": "¿Cómo quieres que sea tu asistente?"
                            },
                            {
                                "type": "TextInput",
                                "label": "Nombre del asistente",
                                "name": "assistant_name",
                                "required": True
                            },
                            {
                                "type": "RadioButtonsGroup",
                                "label": "Estilo de lenguaje",
                                "name": "language_style",
                                "data-source": "${data.language_styles}",
                                "required": True
                            },
                            {
                                "type": "RadioButtonsGroup",
                                "label": "Nivel de experiencia",
                                "name": "experience_level",
                                "data-source": "${data.experience_levels}",
                                "required": True
                            },
                            {
                                "type": "Footer",
                                "label": "Siguiente",
                                "on-click-action": {
                                    "name": "data_exchange",
                                    "payload": {
                                        "assistant_name": "${form.assistant_name}",
                                        "language_style": "${form.language_style}",
                                        "experience_level": "${form.experience_level}"
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        },
        {
            "id": "CONFIG_PREFERENCES",
            "title": "Preferencias de Predicción",
            "terminal": True,
            "data": {
                "prediction_types": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"}
                        }
                    },
                    "__example__": [
                        {"id": "resultado", "title": "Resultado del partido"},
                        {"id": "goles", "title": "Cantidad de goles"},
                        {"id": "cuotas", "title": "Cuotas y apuestas"},
                        {"id": "jugadores", "title": "Rendimiento de jugadores"}
                    ]
                }
            },
            "layout": {
                "type": "SingleColumnLayout",
                "children": [
                    {
                        "type": "Form",
                        "name": "preferences_form",
                        "children": [
                            {
                                "type": "TextSubheading",
                                "text": "¿Qué tipo de predicciones te interesan?"
                            },
                            {
                                "type": "CheckboxGroup",
                                "label": "Selecciona una o más opciones",
                                "name": "prediction_types",
                                "data-source": "${data.prediction_types}",
                                "required": True
                            },
                            {
                                "type": "Footer",
                                "label": "Finalizar",
                                "on-click-action": {
                                    "name": "complete",
                                    "payload": {
                                        "prediction_types": "${form.prediction_types}",
                                        "assistant_name": "${data.assistant_name}",
                                        "language_style": "${data.language_style}",
                                        "experience_level": "${data.experience_level}",
                                        "flow_id": "29413975518246941"
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        }
    ]
}

# JSON para el flujo de actualización de datos de usuario
UPDATE_DATA_FLOW_JSON = {
    "version": "7.0",
    "data_api_version": "3.0",
    "routing_model": {
        "WELCOME_SCREEN": ["USER_DATA"],
        "USER_DATA": []
    },
    "screens": [
        {
            "id": "WELCOME_SCREEN",
            "title": "Actualiza tus Datos",
            "data": {
                "welcome_text": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "__example__": [
                        "👤 *Actualiza tu Perfil*\n\nPor favor completa o actualiza tus datos para una mejor experiencia.",
                        "Esta información nos ayudará a personalizar el contenido y las recomendaciones para ti.",
                        "¡Comencemos! 👇"
                    ]
                }
            },
            "layout": {
                "type": "SingleColumnLayout",
                "children": [
                    {
                        "type": "Image",
                        "src": "https://deep90.com/assets/img/logo/logo-deep-azul.png",
                        "height": 60,
                        "scale-type": "cover"
                    },
                    {
                        "type": "TextBody",
                        "markdown": True,
                        "text": "${data.welcome_text}"
                    },
                    {
                        "type": "Footer",
                        "label": "Comenzar",
                        "on-click-action": {
                            "name": "data_exchange",
                            "payload": {}
                        }
                    }
                ]
            }
        },
        {
            "id": "USER_DATA",
            "title": "Datos Personales",
            "terminal": True,
            "data": {
                "form_description": {
                    "type": "string",
                    "__example__": "Por favor ingresa tus datos personales:"
                }
            },
            "layout": {
                "type": "SingleColumnLayout",
                "children": [
                    {
                        "type": "TextBody",
                        "text": "${data.form_description}"
                    },
                    {
                        "type": "Form",
                        "name": "personal_data_form",
                        "children": [
                            {
                                "type": "TextInput",
                                "required": True,
                                "label": "Nombre completo",
                                "name": "full_name"
                            },
                            {
                                "type": "CalendarPicker",
                                "required": False,
                                "label": "Fecha de nacimiento",
                                "name": "birth_date",
                                "helper-text": "Seleccione su fecha de nacimiento",
                                "mode": "single"
                            },
                            {
                                "type": "TextInput",
                                "required": False,
                                "label": "País",
                                "name": "country"
                            },
                            {
                                "type": "TextInput",
                                "required": False,
                                "label": "Ciudad",
                                "name": "city"
                            },
                            {
                                "type": "TextInput",
                                "input-type": "email",
                                "required": True,
                                "label": "Correo electrónico",
                                "name": "email"
                            },
                            {
                                "type": "Footer",
                                "label": "Finalizar",
                                "on-click-action": {
                                    "name": "complete",
                                    "payload": {
                                        "full_name": "${form.full_name}",
                                        "birth_date": "${form.birth_date}",
                                        "country": "${form.country}",
                                        "city": "${form.city}",
                                        "email": "${form.email}",
                                        "flow_id": "670028658971755"
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        }
    ]
}
