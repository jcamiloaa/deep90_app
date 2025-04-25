# Deep90 App Interaction Overview

Este archivo describe el flujo general de interacción entre las aplicaciones, desde la llegada de un mensaje hasta la respuesta, indicando qué tareas usan Celery, cómo se valida un webhook de WhatsApp y cómo funcionan los servicios y endpoints de los Flows de WhatsApp (incluyendo el cifrado). Se incluye un diagrama de arquitectura para visualizar el proceso completo.

This document describes the general flow of interactions within the `deep90_app` Django project, focusing on how WhatsApp messages are received, processed, and responded to.

## Core Components

*   **`deep90_app.users`**: Manages standard Django user authentication (likely for web interface/admin).
*   **`deep90_app.apps.sports_data`**: Handles fetching, storing, and providing access to football match data (fixtures, results, leagues, etc.).
*   **`deep90_app.apps.whatsapp`**: The core application for interacting with users via the WhatsApp Business API. It manages users (`WhatsAppUser`), conversations, messages, webhooks, flows, and interactions with the OpenAI assistant.

## Message Handling Flow

The process begins when a user sends a message or interacts with a flow via WhatsApp.

1.  **Webhook Reception**:
    *   WhatsApp sends an HTTP request (GET for verification, POST for events) to the `/whatsapp/webhook/` endpoint, handled by `WhatsAppWebhookView`.

2.  **Webhook Verification (GET)**:
    *   The `get` method in `WhatsAppWebhookView` uses `WhatsAppService.verify_webhook` to check `hub.mode`, `hub.verify_token`, and respond with `hub.challenge` if valid.

3.  **Event Reception (POST)**:
    *   The `post` method in `WhatsAppWebhookView` receives incoming events (messages, status updates, flow form submissions).
    *   **Signature Verification**: *Note: The `verify_signature` function exists but doesn't seem to be actively used in the provided `WhatsAppWebhookView.post` method. If enabled by Meta, this step would involve using the `X-Hub-Signature-256` header and the app's private key (`WHATSAPP_PRIVATE_KEY_PATH`) to verify the request body's integrity using HMAC-SHA256.*
    *   The request body is parsed as JSON.
    *   The code iterates through `entry` and `changes` to find message-related events (`field == 'messages'`).

4.  **Message Parsing & Initial Logging**:
    *   The `_handle_messages` method extracts message details (`id`, `type`, `content`) and contact information (`wa_id`, `profile.name`).
    *   The incoming message (including full webhook JSON) is logged immediately to the `Message` model via `WhatsAppService.log_message` for traceability, associated with a `WhatsAppUser`.

5.  **Asynchronous Processing (Celery)**:
    *   The `process_whatsapp_message` Celery task is queued with the contact and message data. This prevents blocking the webhook response.

6.  **`process_whatsapp_message` Task Execution**:
    *   **User Identification**: Gets or creates a `WhatsAppUser` based on `wa_id`. Sends a welcome message if the user is new.
    *   **Checks**: Verifies if the user is blacklisted or if a FREE user has exceeded the `DAILY_MESSAGES_LIMIT`. If so, sends an appropriate message and stops processing.
    *   **Activity Update**: Updates the user's `last_activity` timestamp.
    *   **Message Type Routing**:
        *   **Text**: Calls `process_text_message`.
        *   **Interactive (Button/List Reply)**: Converts the reply ID into a text format (e.g., `button:button_id`) and calls `process_text_message`.
        *   **Interactive (Flow Reply - `nfm_reply`)**: Calls `process_flow_reply`.
        *   **Location**: Converts coordinates to text and calls `process_text_message`.
        *   **Flow (Deprecated?)**: Also calls `process_flow_reply`.
        *   **Other Types**: Sends a generic "cannot process" message.

7.  **`process_text_message` Task Logic**:
    *   Handles special commands (`menu`, `salir`/`exit`).
    *   Handles converted list/button replies (e.g., `list:profile`).
    *   Checks if the user is in "assistant mode" (has an active `Conversation`). If not, displays the main menu.
    *   **Conversation Management**:
        *   Finds or creates an active `Conversation` (potentially reactivating a preserved `GENERAL` one).
        *   Creates an OpenAI thread if needed (`AssistantManager.create_thread`).
    *   **Database Logging**: Saves the user's message to the `Message` model within the conversation.
    *   **OpenAI Interaction**:
        *   Adds the user's message to the OpenAI thread (`AssistantManager.add_message_to_thread`).
        *   Determines the correct Assistant ID based on `ConversationType` or user plan (`AssistantManager.get_assistant_for_user`).
        *   Runs the assistant (`AssistantManager.run_assistant`).
        *   Sends a "Processing..." message to the user.
        *   Queues the `process_assistant_run` task (implementation not fully shown) to poll for the assistant's response.

8.  **`process_flow_reply` Task Logic**:
    *   Parses `response_json` from the flow reply.
    *   Identifies the flow (e.g., `WHATSAPP_FLOW_LIVE_RESULT`).
    *   Handles specific actions selected within the flow (e.g., `action_finish`, `action_predictions`).
    *   If an action requires assistant interaction (like predictions), it calls `start_specialized_assistant_conversation`.

9.  **`start_specialized_assistant_conversation` Task Logic**:
    *   Deactivates any current conversation.
    *   Determines the `ConversationType` based on the requested action/assistant.
    *   Finds or creates a `Conversation` (potentially reusing one for the same `fixture_id` and `type`).
    *   Sends a "Specialized Assistant Mode Activated" message.
    *   Adds context and the initial prompt to the OpenAI thread.
    *   Runs the specialized assistant and queues `process_assistant_run`.

10. **Assistant Response Handling (via `process_assistant_run` / `AssistantWebhookView`)**:
    *   *(Inferred/Partially Shown)*: When the OpenAI Assistant run completes (`thread.run.completed` event via `AssistantWebhookView` or polling via `process_assistant_run`), the system retrieves the assistant's response messages (`AssistantManager.get_assistant_messages`).
    *   The response content is logged to the `Message` model.
    *   The response is sent back to the user via `WhatsAppService.send_text_message`.
    *   If the run requires `tool_calls`, `AssistantManager.process_tool_calls` executes the necessary functions (e.g., `FootballDataService.get_live_match_results`) and submits the output back to OpenAI.

## WhatsApp Flows (Encrypted Endpoint)

WhatsApp Flows allow for richer, form-based interactions within WhatsApp. The `FootballDataFlow` is an example.

1.  **Flow Initiation**: The user interacts with a message sent by `WhatsAppService.send_live_results_flow` (or similar).
2.  **Data Endpoint Request**: As the user navigates the flow screens, WhatsApp makes POST requests to the configured Data Endpoint URL (`/whatsapp/football-flow-data/`), handled by `FootballFlowDataView`.
3.  **Decryption**:
    *   The `post` method receives `encrypted_flow_data`, `encrypted_aes_key`, and `initial_vector`.
    *   `crypto.decrypt_request` uses the server's private key (`WHATSAPP_PRIVATE_KEY_PATH`) to decrypt the AES key (using RSA-OAEP) and then uses the decrypted AES key and IV to decrypt the flow data (using AES-GCM).
4.  **Flow Logic**:
    *   The decrypted data (containing the current screen, user input, action like `INIT`, `data_exchange`, `BACK`) is passed to `FootballDataFlow.handle_flow_request`.
    *   This class method determines the next screen based on the current state and user input, potentially fetching data from `FixtureData` or `LeagueData`.
5.  **Response Logging**: The decrypted request and the generated response data are logged via `WhatsAppService.log_message` for traceability.
6.  **Encryption**:
    *   The response data dictionary (containing the next screen definition and data) is passed to `crypto.encrypt_response`.
    *   It uses the same AES key and a flipped IV to encrypt the response JSON (using AES-GCM).
7.  **Endpoint Response**: The base64-encoded encrypted response is sent back to WhatsApp with a `text/plain` content type.

## Celery Tasks

*   **`process_whatsapp_message(contact_data, message_data)`**: The main entry point for processing incoming messages asynchronously. Handles user checks, routing based on message type, and initiating assistant interactions.
*   **`process_text_message(whatsapp_user, message_id, text)`**: Handles text-based inputs, including commands, list/button replies, and regular chat messages intended for the assistant. Manages conversation state and calls the OpenAI Assistant.
*   **`process_flow_reply(whatsapp_user, message_id, nfm_data)`**: Handles replies coming from interactive flows (`nfm_reply`). Parses the response and triggers appropriate actions, potentially starting specialized assistant conversations.
*   **`start_specialized_assistant_conversation(...)`**: Sets up and starts a conversation with a specific assistant (Predictions, Live Odds, Betting) based on user actions within flows.
*   **`process_assistant_run(...)`**: *(Implementation partially inferred)* Likely polls the OpenAI API (`AssistantManager.check_run_status`) to check if an assistant run is complete or requires action (tool calls). Handles retrieving the final response or triggering tool processing.
*   **`process_assistant_response(...)`**: *(Mentioned in `AssistantWebhookView` but not defined in `tasks.py`)* If using OpenAI webhooks instead of polling, this task would be triggered by `AssistantWebhookView` upon receiving a `thread.run.completed` event to fetch and send the assistant's response.

## Architecture Diagram (ASCII)

```
+-------------------+        +-----------+        +--------+        +---------------------+
| WhatsApp User     | -----> | WhatsApp  | -----> | Proxy  | -----> | Nginx              |
+-------------------+        +-----------+        +--------+        +---------------------+
                                                                      |
                                                                      v
                                                        +-----------------------------+
                                                        | Deep90 Django App           |
                                                        +-----------------------------+
                                                        |  - Processes Webhook        |
                                                        |  - Validates signature      |
                                                        |  - Enqueues Celery task     |
                                                        +-----------------------------+
                                                                      |
                                                                      v
                                                        +-----------------------------+
                                                        | Celery Worker               |
                                                        +-----------------------------+
                                                        |  - Processes message        |
                                                        |  - Calls OpenAI/Flows       |
                                                        +-----------------------------+
                                                                      |
                                                                      v
                                                        +-----------------------------+
                                                        | OpenAI / Flow Handler       |
                                                        +-----------------------------+
                                                                      |
                                                                      v
                                                        +-----------------------------+
                                                        | WhatsApp User (reply)       |
                                                        +-----------------------------+
```

This diagram summarizes the main flow: from the user sending a message, through the various services, to receiving the reply, including async processing and encrypted flows.

