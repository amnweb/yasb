import json
import re
import urllib.request

from settings import BUILD_VERSION


def get_latest_github_release():
    """Fetch the latest release tag from GitHub API. Returns (tag, url) or (None, None) on error."""
    api_url = "https://api.github.com/repos/amnweb/yasb/releases/latest"
    try:
        with urllib.request.urlopen(api_url, timeout=3) as response:
            data = json.loads(response.read().decode())
            tag = data.get("tag_name", "")
            url = data.get("html_url", "")
            return tag, url
    except Exception:
        return None, None


def version_tuple(v):
    """Convert version string to tuple of ints for comparison."""
    v = v.lstrip("vV")
    return tuple(int(x) for x in re.findall(r"\d+", v))


def maybe_answer_yasb_question(messages):
    """
    This is very simple helper because some Ai does not have access to the internet or knowledge about YASB.
    If the last user message is a YASB-specific version question, return an answer string.
    Otherwise, return None.
    """
    if not messages or not isinstance(messages[-1], dict):
        return None
    content = messages[-1].get("content", "")
    # Handle multimodal content (list of parts) - get first text block (user's text, not attachments)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                if "[Attachment: " not in part.get("text", ""):
                    content = part.get("text", "")
                    break
        else:
            content = ""
    if not isinstance(content, str):
        return None
    user_text = content.lower().strip()
    # Only answer if the question is about YASB
    if (
        ("yasb" in user_text)
        and re.search(r"(version|release)", user_text)
        and re.search(r"(what|which|current|check|give|tell|about|info|information|how|find|see)", user_text)
    ):
        version = BUILD_VERSION
        release_url = f"https://github.com/amnweb/yasb/releases/tag/v{version}"
        latest_tag, latest_url = get_latest_github_release()
        answer = f'YASB version: {version}<br><a href="{release_url}">View release info</a>'
        # Add CLI helper if user asks how to check/find/see version
        if (
            ("how" in user_text)
            and ("check" in user_text or "find" in user_text or "see" in user_text)
            and "version" in user_text
        ):
            answer += "<br>To check your YASB version from the command line, run:<br><code>yasbc --version</code>"
            answer += "<br>For all available commands, run: <code>yasbc --help</code>"
        if latest_tag and version_tuple(latest_tag) > version_tuple(version):
            answer += f'<br><b>New version available:</b> {latest_tag} <a href="{latest_url}">Download here</a>'
        return answer
    return None


def format_chat_text(text):
    """
    Format chat text to HTML with basic Markdown support.
    NOTE: This function is still a work in progress and may not cover all edge cases.
    """
    if not text:
        return text

    def repl(match):
        # Preprocess markdown links: [label](url) or [url](url) to just url if label is a url, else 'label: url'
        label, url = match.group(1), match.group(2)
        label_stripped = label.strip()
        if label_stripped.startswith("[") and label_stripped.endswith("]"):
            label_stripped = label_stripped[1:-1]
        if label_stripped == url or re.match(r"https?://", label_stripped):
            return url
        else:
            return f"{label_stripped} {url}"

    text = re.sub(r"\[([^\]]+)]\((https?://[^)]+)\)", repl, text)

    # Remove zero-width spaces
    # text = text.replace("\u200b", "")
    # Escape HTML characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert **bold** to <b>
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    # Convert *italic* to <i>, but not bullet points
    text = re.sub(r"(?<!^)\s\*((?!\*)[^*\n]+?)\*(?!\*)", r" <i>\1</i>", text, flags=re.MULTILINE)

    # Replace inline code with <code>...</code>
    def inline_code_repl(match):
        code = match.group(1)
        return f'<code style="background-color:rgba(0,0,0,0.2);white-space:pre-wrap;">{code}</code>'

    text = re.sub(r"`([^`\n]+)`", inline_code_repl, text)

    # Replace triple backtick code blocks with <pre>...</pre>
    def code_repl(match):
        code = match.group(1)
        return f'<pre style="background-color:rgba(0,0,0,0.2);white-space:pre-wrap">{code}</pre>'

    text = re.sub(r"```(?:[a-zA-Z0-9]*)[ \t]*\r?\n([\s\S]*?)```", code_repl, text)

    # Split by <pre>...</pre> blocks
    parts = re.split(r"(<pre[\s\S]*?>[\s\S]*?<\/pre>)", text)

    def replace_url(match):
        url = match.group(1)
        href = "http://" + url if url.startswith("www.") else url
        display_url = url.rstrip(".,;:!?)")
        href = href.rstrip(".,;:!?)")
        return f'<a href="{href}" style="color: #4A9EFF; text-decoration: underline;">{display_url}</a>'

    # Only apply URL replacement to non-<pre> parts (even indices)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'((?:https?://|ftp://|www\.)[^\s<>"&]+)(?=\s|$|&(?:amp|lt|gt);)', replace_url, parts[i])

    text = "".join(parts)
    text = text.replace("\n", "<br>")
    return text
