# AI Chat Widget

The AI Chat widget provides a flexible, interactive chat interface that works with any provider offering an OpenAI-compatible API (such as OpenAI, Ollama, LocalAI, and others). You can define multiple providers and models in your configuration, and switch between them at runtime—chat history is saved per provider/model combination.


| Option              | Type    | Default         | Description |
|---------------------|---------|-----------------|-------------|
| `label`             | string  | `"AI Chat"`    | The label displayed for the widget. |
| `chat`              | dict    | See example     | Popup menu configuration (blur, corners, etc). |
| `icons`             | dict    | See example     | Icons for send, stop, clear, assistant. |
| `notification_dot`  | dict    | `{'enabled': false, 'corner': 'bottom_left', 'color': 'red', 'margin': [1, 1]}` | A dictionary specifying the notification dot settings for the widget. |
| `animation`    | dict    | `{enabled: true, type: "fadeInOut", duration: 200}` | Animation settings for the widget.                                          |
| `callbacks`    | dict    | `{on_left: "toggle_chat", on_middle: "do_nothing", on_right: "do_nothing"}` | Mouse event callbacks.                  |
| `label_shadow` | dict    | `{enabled: False, color: "black", offset: [1,1], radius: 3}` | Shadow for the label.                   |
| `container_shadow` | dict | `{enabled: False, color: "black", offset: [1,1], radius: 3}` | Shadow for the container.              |
| `providers`         | list    | []              | List of AI providers and their models. |

## Example Configuration

```yaml
ai_chat:
  type: "yasb.ai_chat.AiChatWidget"
  options:
    label: "<span>\uf086</span>"
    chat:
      blur: true
      round_corners: true
      round_corners_type: "normal"
      border_color: "system"
      alignment: "center"
      direction: "down"
      offset_left: 0
      offset_top: 6
    icons:
      attach: "\uf0c6"
      send: "\uf1d8"
      stop: "\uf04d"
      clear: "\uf1f8"
      assistant: "\udb81\ude74"
    notification_dot:
      enabled: false
      corner: "top_right"
      color: "red"
      margin: [ 0, 2 ]
    callbacks:
      on_left: "toggle_chat"
    providers:
      - provider: "Ollama"
        api_endpoint: "http://localhost:11434/v1"
        credential: "ollama"
        models: 
        - name: "gemma3:1b"
          label: "Gemma3"
      - provider: "OpenAI"
        api_endpoint: "https://api.openai.com/v1"
        credential: "dsfsfsfs65sd6f56sd5f6"
        models:
        - name: "gpt-3.5-turbo"
          label: "GPT3.5 Turbo"
        - name: "gpt-4"
          label: "GPT4"
          default: true
          temperature: 0.3
          top_p: 0.95
          max_tokens: 4096
          max_image_size: 1024
          max_attachment_size: 256
          instructions: "C:/Users/amnweb/Desktop/custom_gpt_chatmode.md"

```

**Key features:**
- Works with any API that returns OpenAI-compatible responses (chat/completions format)
- Supports multiple providers and models, selectable in the popup menu
- API keys or credentials can be stored securely in environment variables or directly in the config file
- Streaming responses with real-time updates
- Persistent chat history per provider/model, restored automatically when switching
- Context menu for copying messages (selected or all)
- Customizable icons, padding, shadows, and mouse callbacks
- Robust error handling and reconnection for streaming
- Supports system prompts/instructions as strings or external markdown files
- Notification dot for new messages when the chat is closed
- File attachments (images and text files) with automatic compression/truncation based on model limits

**Usage:**
- Click the widget to open the chat popup
- Select your provider and model from the dropdown menus
- Attach files with the attach button (images and text files supported)
  - Images are automatically compressed if they exceed the model's `max_image_size` limit
  - Text files are automatically truncated if they exceed the model's `max_attachment_size` limit
  - Binary files (PDFs, executables, etc.) are rejected as unsupported
  - Set `max_image_size: 0` to disable image attachments for a model
  - Set `max_attachment_size: 0` to disable text file attachments for a model
- Enter your message and send; responses stream in real time
- Switch providers/models at any time—your chat history is preserved
- API credentials can be set as environment variables (recommended for security) or in the config file
- Instructions for the AI can be provided as a string or as a path to a markdown file ending with `_chatmode.md`

This widget is ideal for integrating any LLM service that follows the OpenAI API format, making it easy to add new providers or models without code changes.


## Description of Options

- **label:** The label displayed for the widget.
- **auto_focus_input:** Automatically focus the input field when the chat window is opened.
- **chat:** Dictionary for popup menu appearance.
  - **blur**: Enable blur effect
  - **round_corners**: Enable system rounded corners
  - **round_corners_type**: Type of corners (e.g., `"normal"` or `"small"`)
  - **border_color**: Border color (`"system"`, `HEX` color, `None`)
  - **alignment**: Menu alignment ("left", "center", "right")
  - **direction**: Popup direction ("up", "down")
  - **offset_left**: Horizontal offset from the widget
  - **offset_top**: Vertical offset from the widget
- **icons:** Dictionary of icons for send, stop, clear, and assistant. Can be icon fonts or simple text.
  - **send** Icon for sending messages
  - **attach** Icon for the attachment button
  - **stop**: Icon for stopping streaming
  - **clear**: Icon for clearing chat history
  - **assistant**: Icon for the assistant avatar
- **notification_dot:** Dictionary for notification dot settings. This allows you to show a small dot indicating new messages when the chat is closed.
  - **enabled:** Enable notification dot.
  - **corner:** Set the corner where the dot should appear.
  - **color:** Set the color of the notification dot. Can be hex or string color.
  - **margin:** Set the x, y margin for the notification dot.
- **animation:** Animation settings for popup and chat area.
  - **enabled**: Enable/disable animation
  - **type**: Animation type (e.g., "fadeInOut")
  - **duration**: Duration in ms
- **callbacks:** Mouse event callbacks. Keys:
  - **on_left**: Action for left click (e.g., "toggle_menu")
  - **on_middle**: Middle click action
  - **on_right**: Right click action
- **label_shadow:** Shadow options for the label.
- **container_shadow:** Shadow options for the container.
- **providers:** List of provider configs. Each provider has:
  - **provider**: Name (e.g., "OpenAI")
  - **models**: List of models, each with:
    - **name**: Model name
    - **label**: Display label
    - **default**: Optionally mark this provider+model as the default selection (only one model per widget should have this set to `true`)
    - **max_tokens**: Max tokens per response
    - **temperature**: Sampling temperature
    - **top_p**: Nucleus sampling
    - **instructions**: System prompt or path to instructions file
    - **max_image_size**: Maximum image attachment size in KB (default: 0, disabled). Images larger than this will be compressed automatically
    - **max_attachment_size**: Maximum text file attachment size in KB (default: 256). Text files larger than this will be truncated



> [!IMPORTANT]  
> Ai Chat widget uses the `QMenu` for the context menu, which supports various styles. You can customize the appearance of the menu using CSS styles. For more information on styling, refer to the [Context Menu Styling](https://github.com/amnweb/yasb/wiki/Styling#context-menu-styling)
If you want to use different styles for the context menu, you can target the `.ai-chat-popup .context-menu` class to customize the appearance of the Ai Chat widget menu.

## Available Styles
```css
.ai-chat-widget {}
.ai-chat-widget .widget-container {}
.ai-chat-widget .widget-container .label {}
.ai-chat-widget .widget-container .icon {}

/* Chat popup */
.ai-chat-popup {} /* Chat popup container */
.ai-chat-popup .chat-header {} /* Header of the chat popup */
.ai-chat-popup .chat-content {} /* Content of the chat popup */
.ai-chat-popup .chat-footer {} /* Footer of the chat popup */

.ai-chat-popup .chat-header .provider-label {} /* Provider label in header */
.ai-chat-popup .chat-header .model-label {} /* Model label in header */
.ai-chat-popup .chat-header .provider-button {} /* Provider selection button */
.ai-chat-popup .chat-header .model-button {} /* Model selection button */

/* Context menu */
.ai-chat-popup .chat-header .context-menu {} /* Context menu for chat header */
.ai-chat-popup .context-menu {} /* Context menu for chat content */

/* Empty state */
.ai-chat-popup .chat-content .empty-chat .greeting {} /* Greeting message in empty chat */
.ai-chat-popup .chat-content .empty-chat .message {} /* Message in empty chat */

/* Chat messages */
.ai-chat-popup .chat-content .user-message {} /* User message style */
.ai-chat-popup .chat-content .assistant-message {} /* Assistant message style */
.ai-chat-popup .chat-content .assistant-icon {} /* Icon for assistant messages */

/* Input area */
.ai-chat-popup .chat-footer .attach-button {} /* Attachment button */
.ai-chat-popup .chat-footer .chat-input {} /* Input area for chat messages */
.ai-chat-popup .chat-footer .send-button {} /* Send button in input area */
.ai-chat-popup .chat-footer .stop-button {} /* Stop button in input area */
.ai-chat-popup .chat-footer .clear-button {} /* Clear button in input area */

/* Attachments row */
.ai-chat-popup .attachment-chip {} /* Attachment chip container */
.ai-chat-popup .attachment-label {} /* Attachment filename text */
.ai-chat-popup .attachment-remove-button {} /* Remove (x) button on chip */
```


## Example CSS
```css

.ai-chat-widget {
    padding: 0 6px 0 6px;
}
.ai-chat-widget .icon {
    color: #89b4fa;
    font-size: 16px;
}
.ai-chat-popup {
    background-color: rgba(24, 25, 27, 0.8);
    min-width: 500px;
    max-width: 500px;
    min-height: 600px;
    max-height: 600px;
}
.ai-chat-popup .chat-header {
    background-color: rgba(24, 25, 27, 0.4);
    padding: 16px;
}
.ai-chat-popup .chat-footer {
    background-color: rgba(24, 25, 27, 0);
    padding: 16px;
 
}
.ai-chat-popup .chat-header .provider-label,
.ai-chat-popup .chat-header .model-label {
    font-family: 'Segoe UI';
    font-size: 14px;
    color: #ffffff;
    margin-right: 8px;
    font-weight: 600;
}
.ai-chat-popup .chat-header .provider-button,
.ai-chat-popup .chat-header .model-button {
    font-family: 'Segoe UI';
    background-color: #202020;
    border: 1px solid rgba(255, 255, 255, 0.2);
    font-size: 13px;
    color: #ffffff;
    margin-right: 8px;
    min-width: 130px;
    max-width: 130px;
    border-radius: 6px;
    padding: 4px 10px;
}
.ai-chat-popup .chat-header .provider-button:disabled,
.ai-chat-popup .chat-header .model-button:disabled {
    color: rgba(255, 255, 255, 0.5);
}

/* Context menu styles for header and chat content */
.ai-chat-popup .context-menu {
    background-color: #202020;
    border: none;
    padding: 4px 0px;
    font-family: 'Segoe UI';
    font-size: 12px;
    color: #FFFFFF;
}
.ai-chat-popup .context-menu::separator {
    height: 1px;
    background-color: #404040;
    margin: 4px 8px;
}
 
.ai-chat-popup .context-menu::item {
    background-color: transparent;
    padding: 6px 12px;
    margin: 2px 6px;
    border-radius: 4px;
    min-width: 100px;
}
/* Context menu item styles for header dropdown */
.ai-chat-popup .chat-header .context-menu::item {
    min-width: 130px;
    max-width: 130px;
    padding: 4px;
}
.ai-chat-popup .context-menu::item:disabled {
    color: #666666;
} 
.ai-chat-popup .context-menu::item:selected {
    background-color: #3a3a3a;
    color: #FFFFFF;
}
.ai-chat-popup .context-menu::item:checked {
    background-color: #0078d7;
    color: #FFFFFF;
}
 

.ai-chat-popup .chat-content {
    background-color: rgba(206, 10, 10, 0);
    border: none;
}
.ai-chat-popup .chat-content .empty-chat .greeting,
.ai-chat-popup .chat-content .empty-chat .message {
    color: rgba(255, 255, 255, 0.8);
    font-family: 'Segoe UI';
    font-size: 48px;
    font-weight: 600;
}
.ai-chat-popup .chat-content .empty-chat .message {
    color: rgba(255, 255, 255, 0.4);
    font-size: 24px;
    padding-top: 8px;
    
}
.ai-chat-popup .chat-content .user-message,
.ai-chat-popup .chat-content .assistant-message {
    color: #ffffff;
    padding: 8px;
    border-radius: 4px;
    margin: 4px 0;
    font-family: 'Segoe UI';
    font-size: 14px;
}
.ai-chat-popup .chat-content .user-message {
    margin-left: 26px;
}
.ai-chat-popup .chat-content .assistant-message {
    background-color: rgba(162, 168, 187, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.ai-chat-popup .chat-content .assistant-icon {
    font-size: 24px;
    color: #8c8d92;
    margin-right: 8px;
    font-family: "JetBrainsMono NFP";
}

.ai-chat-popup .chat-footer .chat-input {
    background-color: rgba(24, 25, 27, 0.6);
    border: 2px solid  #2d2d2d;
    border-radius: 4px;
    padding: 0 8px;
    font-family: 'Segoe UI';
    font-size: 14px;
    color: #ffffff;
    margin-top: 8px;
    max-height: 28px;
    min-height: 28px;
}
.ai-chat-popup .chat-footer .chat-input:focus {
    border-color: #0078d7;
}
.ai-chat-popup .chat-footer .clear-button,
.ai-chat-popup .chat-footer .send-button,
.ai-chat-popup .chat-footer .stop-button,
.ai-chat-popup .chat-footer .attach-button {
    background-color: #2d2d2d;
    color: #ffffff;
    font-size: 12px;
    max-width: 30px;
    min-width: 30px;
    max-height: 30px;
    min-height: 30px;
    border-radius: 4px;
    margin-top: 8px;
    border: none;
    font-family: "JetBrainsMono NFP";
}
.ai-chat-popup .chat-footer .stop-button {
    background-color: #0078d7;
}
.ai-chat-popup .chat-footer .clear-button:hover,
.ai-chat-popup .chat-footer .send-button:hover,
.ai-chat-popup .chat-footer .stop-button:hover,
.ai-chat-popup .chat-footer .attach-button:hover {
    background-color: #464646;
}
.ai-chat-popup .chat-footer .clear-button:disabled,
.ai-chat-popup .chat-footer .send-button:disabled,
.ai-chat-popup .chat-footer .stop-button:disabled,
.ai-chat-popup .chat-footer .attach-button:disabled {
    background-color: #2d2d2d;
    color: #818181;
}
```
## Troubleshooting & Best Practices

- Ensure provider/model configs are correct and available.
- Ensure API credentials are valid and have access to the specified models.
- Endpoints must be return valid responses with openai-compatible formats.
- If instructions are a file path, it must end with `_chatmode.md` and be accessible.
- If streaming fails, check network/API credentials and error messages.

> [!NOTE]
> AI Chat widget supports toggle visibility using the `toggle-widget ai_chat` command in the CLI. More information about the CLI commands can be found in the [CLI documentation](https://github.com/amnweb/yasb/wiki/CLI#toggle-widget-visibility).

## Preview of the Widget
![AI Chat YASB Widget](assets/ec1b9764-1a027260-3e58-1f50-e78022a4eede.png)