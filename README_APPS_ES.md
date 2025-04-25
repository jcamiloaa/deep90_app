# Deep90 App: Descripción General de la Interacción

Este documento explica el flujo general de interacción entre las aplicaciones del proyecto `deep90_app`, desde la recepción de un mensaje de WhatsApp hasta la respuesta, indicando qué tareas usan Celery, cómo se valida un webhook de WhatsApp y cómo funcionan los servicios y endpoints de los Flows de WhatsApp (incluyendo el cifrado).

## Componentes Principales

* **`deep90_app.users`**: Gestión de usuarios y autenticación.
* **`deep90_app.apps.sports_data`**: Obtención y gestión de datos de fútbol (partidos, ligas, resultados, etc.).
* **`deep90_app.apps.whatsapp`**: Núcleo de la integración con WhatsApp Business API. Gestiona usuarios, mensajes, webhooks, flujos y la interacción con el asistente OpenAI.

## Flujo General de Mensajes

1. **Recepción del Webhook**:
    * WhatsApp envía una petición HTTP (GET para verificación, POST para eventos) al endpoint `/whatsapp/webhook/`.

2. **Verificación del Webhook (GET)**:
    * Se valida el token (`hub.verify_token`) y se responde con el challenge si es correcto.

3. **Recepción de Eventos (POST)**:
    * Se recibe el evento (mensaje, actualización de estado, respuesta de flow, etc.).
    * **Validación de Firma**: Si está habilitada, se verifica la firma HMAC-SHA256 usando la cabecera `X-Hub-Signature-256` y la clave privada (`private_key.pem`).
    * Se procesa el JSON recibido y se identifican los eventos de mensajes.

4. **Registro Inicial del Mensaje**:
    * Se extraen los datos del mensaje y del contacto.
    * Se registra el mensaje completo en la base de datos para trazabilidad.

5. **Procesamiento Asíncrono (Celery)**:
    * Se encola la tarea `process_whatsapp_message` en Celery para procesar el mensaje sin bloquear la respuesta al webhook.

6. **Ejecución de la Tarea `process_whatsapp_message`**:
    * Identifica o crea el usuario de WhatsApp.
    * Verifica límites de uso y listas negras.
    * Actualiza la actividad del usuario.
    * Redirige según el tipo de mensaje:
        * **Texto**: Llama a `process_text_message`.
        * **Interacciones (botón/lista/flow)**: Convierte y redirige a la función correspondiente.
        * **Ubicación**: Convierte coordenadas a texto y procesa.
        * **Otros**: Responde con mensaje genérico.

7. **Lógica de `process_text_message`**:
    * Procesa comandos especiales (`menu`, `salir`, etc.).
    * Gestiona el estado de la conversación y la interacción con el asistente OpenAI.
    * Registra el mensaje y encola la tarea `process_assistant_run` para esperar la respuesta del asistente.

8. **Lógica de `process_flow_reply`**:
    * Procesa respuestas de flujos interactivos (Flows de WhatsApp).
    * Identifica acciones y puede iniciar conversaciones especializadas con asistentes.

9. **Lógica de Flujos Especializados**:
    * Desactiva conversaciones previas y activa la especializada según el flujo.
    * Añade contexto y encola la tarea para el asistente.

10. **Recepción y Envío de Respuesta del Asistente**:
    * Cuando el asistente responde (por polling o webhook), se registra y se envía la respuesta al usuario por WhatsApp.
    * Si requiere acciones (tool calls), se ejecutan y se reenvía el resultado al asistente.

## Flujos de WhatsApp (Endpoints Encriptados)

1. **Inicio del Flow**: El usuario interactúa con un mensaje de flow.
2. **Petición al Endpoint de Datos**: WhatsApp hace POST a `/whatsapp/football-flow-data/`.
3. **Desencriptado**: Se desencripta el payload usando la clave privada (`private_key.pem`).
4. **Lógica del Flow**: Se procesa la pantalla y acción actual, consultando datos si es necesario.
5. **Registro**: Se registra la petición y respuesta desencriptada.
6. **Encriptado de Respuesta**: Se encripta la respuesta usando la misma clave y se responde a WhatsApp.

## Tareas en Celery

* `process_whatsapp_message`: Procesamiento principal de mensajes entrantes.
* `process_text_message`: Procesamiento de mensajes de texto y comandos.
* `process_flow_reply`: Procesamiento de respuestas de flows.
* `start_specialized_assistant_conversation`: Inicia conversaciones especializadas.
* `process_assistant_run`: Espera y gestiona la respuesta del asistente.

## Diagrama de Arquitectura (Mermaid)


```mermaid
sequenceDiagram
    participant Usuario as WhatsApp User
    participant WhatsApp
    participant Traefik as Load Balancer (Prod)
    participant Nginx as Web Server (Prod)
    participant DjangoApp as Deep90 Django App
    participant Celery as Celery Worker
    participant Redis
    participant PostgreSQL as DB
    participant OpenAI

    Usuario->>+WhatsApp: Envía mensaje
    WhatsApp->>+Traefik: POST /whatsapp/webhook/
    Traefik->>Nginx: Reenvía petición
    Nginx->>+DjangoApp: Webhook recibido
    DjangoApp->>Redis: Encola tarea Celery
    DjangoApp-->>-Nginx: HTTP 200 OK
    Nginx-->>Traefik: HTTP 200 OK
    Traefik-->>-WhatsApp: HTTP 200 OK

    Redis->>+Celery: Ejecuta tarea
    Celery->>+PostgreSQL: Busca/crea usuario
    Celery->>Celery: Verifica límites/listas
    alt Mensaje de texto
        Celery->>Celery: process_text_message
        Celery->>+PostgreSQL: Conversación
        Celery->>+OpenAI: Interacción asistente
        Celery->>Redis: Encola process_assistant_run
    else Respuesta de flow
        Celery->>Celery: process_flow_reply
        opt Asistente especializado
            Celery->>Celery: start_specialized_assistant_conversation
            Celery->>+OpenAI: Interacción asistente
            Celery->>Redis: Encola process_assistant_run
        end
    end
    Celery-->>-Redis: Tarea completa

    Redis->>+Celery: process_assistant_run
    loop Espera respuesta
        Celery->>+OpenAI: Consulta estado
        alt Completado
            OpenAI-->>-Celery: Respuesta
            Celery->>+PostgreSQL: Guarda respuesta
            Celery->>+DjangoApp: Envía respuesta a WhatsApp
            DjangoApp->>+WhatsApp: API mensaje
            WhatsApp-->>-Usuario: Muestra respuesta
            break
        else Requiere acción
            OpenAI-->>-Celery: Tool calls
            Celery->>+PostgreSQL: Ejecuta tool
            Celery->>+OpenAI: Envía resultado
        else En progreso
            Celery->>Redis: Re-encola tarea
            break
        else Fallo
            Celery->>+DjangoApp: Envía error
            DjangoApp->>+WhatsApp: API mensaje
            WhatsApp-->>-Usuario: Muestra error
            break
        end
    end
    Celery-->>-Redis: Tarea completa

    Usuario->>+WhatsApp: Interacción Flow
    WhatsApp->>+Traefik: POST /whatsapp/football-flow-data/
    Traefik->>Nginx: Reenvía
    Nginx->>+DjangoApp: Endpoint Flow
    DjangoApp->>DjangoApp: Desencripta petición
    DjangoApp->>DjangoApp: Procesa lógica Flow
    opt Consulta datos
        DjangoApp->>+PostgreSQL: Consulta
        PostgreSQL-->>-DjangoApp: Resultados
    end
    DjangoApp->>DjangoApp: Encripta respuesta
    DjangoApp-->>-Nginx: Responde encriptado
    Nginx-->>Traefik: Responde
    Traefik-->>-WhatsApp: Responde
    WhatsApp->>-Usuario: Muestra siguiente pantalla
```

---

Este flujo y diagrama resumen la arquitectura y la interacción entre los componentes principales, destacando el uso de Celery y el manejo de endpoints encriptados para los Flows de WhatsApp.