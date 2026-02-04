from typing import Callable


def format_attachments_for_display(attachments: list[dict], size_formatter: Callable[[int], str]) -> str:
    if not attachments:
        return ""

    lines = ["Attachments (sent to AI):"]
    for idx, att in enumerate(attachments, 1):
        info = f"{idx}) {att.get('name')} ({size_formatter(att.get('size', 0))})"
        if att.get("truncated"):
            info += " [truncated]"
        if att.get("compressed"):
            info += " [compressed]"
        lines.append(info)
    return "\n".join(lines)


def compose_user_message(
    user_text: str,
    attachments: list[dict],
    size_formatter: Callable[[int], str],
) -> tuple[str, str]:
    """Return (payload_text, display_text) including any attachments."""
    ready_attachments = [att for att in attachments if not att.get("processing")]
    text_attachments = [att for att in ready_attachments if not att.get("is_image")]

    payload_text = user_text
    if text_attachments:
        lines = ["Attachments:"]
        for idx, att in enumerate(text_attachments, 1):
            lines.append(f"{idx}) {att['prompt']}")
        attachments_text = "\n".join(lines)
        payload_text = f"{user_text}\n\n{attachments_text}" if user_text else attachments_text

    display_text = user_text
    if ready_attachments:
        display_summary = format_attachments_for_display(ready_attachments, size_formatter)
        display_text = f"{user_text}\n\n{display_summary}" if user_text else display_summary

    return payload_text, display_text


def build_api_messages(history: list[dict], provider_type: str) -> list[dict]:
    api_messages: list[dict] = []

    if provider_type == "copilot":
        system_msg = next((m for m in history if m.get("role") == "system"), None)
        last_user = next((m for m in reversed(history) if m.get("role") == "user"), None)
        if not last_user:
            return []

        ready_attachments = [att for att in last_user.get("attachments", []) if not att.get("processing")]
        image_attachments = [att for att in ready_attachments if att.get("is_image")]
        prompt_text = last_user.get("content") or last_user.get("user_text") or ""

        if system_msg:
            api_messages.append({"role": "system", "content": system_msg.get("content", "")})

        message_payload = {"role": "user", "content": prompt_text}
        if image_attachments:
            message_payload["attachments"] = image_attachments
        api_messages.append(message_payload)
        return api_messages

    for msg in history:
        role = msg["role"]
        content = msg["content"]
        attachments = msg.get("attachments", [])

        if attachments and role == "user":
            ready_attachments = [att for att in attachments if not att.get("processing")]
            content_parts = []

            user_text = msg.get("user_text", "")
            if user_text:
                content_parts.append({"type": "text", "text": user_text})

            for att in ready_attachments:
                if att.get("is_image"):
                    content_parts.append({"type": "image_url", "image_url": {"url": att["image_url"]}})
                else:
                    content_parts.append({"type": "text", "text": att["prompt"]})

            api_messages.append({"role": role, "content": content_parts})
        else:
            api_messages.append({"role": role, "content": content})

    return api_messages
