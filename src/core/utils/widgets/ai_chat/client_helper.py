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
    user_text = messages[-1].get("content", "").lower().strip()
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
