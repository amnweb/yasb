import base64
import hashlib
import json
import random
import secrets
import string
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_DEV_TOOLS

_LOREM_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam "
    "quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo "
    "consequat duis aute irure dolor in reprehenderit in voluptate velit esse "
    "cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat "
    "non proident sunt in culpa qui officia deserunt mollit anim id est laborum"
).split()

_TOOLS: dict[str, dict[str, str]] = {
    "uuid": {
        "name": "UUID Generator",
        "description": "Generate random UUID v4 values",
    },
    "hash": {
        "name": "Hash Generator",
        "description": "MD5, SHA1, SHA256, SHA512 hashes of text",
    },
    "base64": {
        "name": "Base64 Encode/Decode",
        "description": "Encode or decode Base64 strings",
    },
    "url": {
        "name": "URL Encode/Decode",
        "description": "Percent-encode or decode URL strings",
    },
    "jwt": {
        "name": "JWT Decoder",
        "description": "Decode JWT token payload (no verification)",
    },
    "lorem": {
        "name": "Lorem Ipsum",
        "description": "Generate placeholder text",
    },
    "ts": {
        "name": "Timestamp Converter",
        "description": "Convert between unix timestamps and dates",
    },
    "pw": {
        "name": "Password Generator",
        "description": "Generate secure random passwords",
    },
}


class DevToolsProvider(BaseProvider):
    """Developer utilities accessible from Quick Launch.

    Type the prefix (default ``dev``) to see available tools, then pick one
    or type a tool name directly, e.g. ``dev uuid``, ``dev hash hello``.
    """

    name = "dev_tools"
    display_name = "Developer Tools"
    icon = ICON_DEV_TOOLS
    input_placeholder = "Pick a tool or type a command..."

    def __init__(self, config: dict | None = None):
        super().__init__(config)

    def match(self, text: str) -> bool:
        if self.prefix:
            stripped = text.strip()
            return stripped == self.prefix or stripped.startswith(self.prefix + " ")
        return True

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip()
        parts = query.split(None, 1)

        if not query:
            return self._tool_tiles()

        tool_key = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        handler = {
            "uuid": self._uuid_results,
            "hash": self._hash_results,
            "base64": self._base64_results,
            "url": self._url_results,
            "jwt": self._jwt_results,
            "lorem": self._lorem_results,
            "ts": self._timestamp_results,
            "pw": self._password_results,
        }.get(tool_key)

        if handler:
            return handler(arg)

        filtered = self._filter_tools(query)
        if filtered:
            return filtered
        return self._tool_tiles()

    def execute(self, result: ProviderResult) -> bool | None:
        data = result.action_data
        copy_text = data.get("copy")
        if copy_text is not None:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(str(copy_text))
            return True
        return None

    def get_context_menu_actions(self, result):
        actions: list[ProviderMenuAction] = []
        data = result.action_data
        if data.get("copy") is not None:
            actions.append(ProviderMenuAction(id="copy", label="Copy to clipboard"))
        return actions

    def execute_context_menu_action(self, action_id, result):
        data = result.action_data
        if action_id == "copy":
            copy_text = data.get("copy", "")
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(str(copy_text))
            return ProviderMenuActionResult(close_popup=True)
        return ProviderMenuActionResult()

    def get_query_text(self, text: str) -> str:
        if self.prefix and text.strip().startswith(self.prefix):
            return text.strip()[len(self.prefix) :].strip()
        return text.strip()

    def _tool_tiles(self) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        for key, info in _TOOLS.items():
            results.append(
                ProviderResult(
                    title=info["name"],
                    description=info["description"],
                    icon_char=ICON_DEV_TOOLS,
                    provider=self.name,
                    action_data={"_home": True, "prefix": self.prefix, "initial_text": key},
                )
            )
        return results

    def _filter_tools(self, query: str) -> list[ProviderResult]:
        q = query.lower()
        results: list[ProviderResult] = []
        for key, info in _TOOLS.items():
            if q in key or q in info["name"].lower() or q in info["description"].lower():
                results.append(
                    ProviderResult(
                        title=info["name"],
                        description=info["description"],
                        icon_char=ICON_DEV_TOOLS,
                        provider=self.name,
                        action_data={"_home": True, "prefix": self.prefix, "initial_text": key},
                    )
                )
        return results

    def _make_result(self, title: str, description: str, copy_text: str) -> ProviderResult:
        return ProviderResult(
            title=title,
            description=description,
            icon_char=ICON_DEV_TOOLS,
            provider=self.name,
            action_data={"copy": copy_text},
        )

    def _uuid_results(self, arg: str) -> list[ProviderResult]:
        count = 5
        if arg.isdigit():
            count = min(int(arg), 20)
        results: list[ProviderResult] = []
        for _ in range(count):
            val = str(uuid.uuid4())
            results.append(self._make_result(val, "Click to copy UUID v4", val))
        return results

    def _hash_results(self, arg: str) -> list[ProviderResult]:
        if not arg:
            return [self._make_result("Type text after 'hash'", "e.g. dev hash hello world", "")]
        data = arg.encode("utf-8")
        results: list[ProviderResult] = []
        for name, func in [
            ("MD5", hashlib.md5),
            ("SHA1", hashlib.sha1),
            ("SHA256", hashlib.sha256),
            ("SHA512", hashlib.sha512),
        ]:
            digest = func(data).hexdigest()
            results.append(self._make_result(digest, f"{name} - Click to copy", digest))
        return results

    def _base64_results(self, arg: str) -> list[ProviderResult]:
        if not arg:
            return [self._make_result("Type text after 'base64'", "Encodes to Base64. Paste Base64 to decode.", "")]
        results: list[ProviderResult] = []
        encoded = base64.b64encode(arg.encode("utf-8")).decode("ascii")
        results.append(self._make_result(encoded, "Base64 Encoded - Click to copy", encoded))
        try:
            decoded = base64.b64decode(arg).decode("utf-8")
            results.append(self._make_result(decoded, "Base64 Decoded - Click to copy", decoded))
        except Exception:
            pass
        return results

    def _url_results(self, arg: str) -> list[ProviderResult]:
        if not arg:
            return [self._make_result("Type text after 'url'", "URL encode/decode a string", "")]
        results: list[ProviderResult] = []
        encoded = urllib.parse.quote(arg, safe="")
        results.append(self._make_result(encoded, "URL Encoded - Click to copy", encoded))
        try:
            decoded = urllib.parse.unquote(arg)
            if decoded != arg:
                results.append(self._make_result(decoded, "URL Decoded - Click to copy", decoded))
        except Exception:
            pass
        return results

    def _jwt_results(self, arg: str) -> list[ProviderResult]:
        if not arg:
            return [self._make_result("Paste a JWT token after 'jwt'", "Decodes the payload (no verification)", "")]
        try:
            parts = arg.split(".")
            if len(parts) < 2:
                return [self._make_result("Invalid JWT", "Expected header.payload.signature format", "")]
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)
            pretty = json.dumps(payload, indent=2, ensure_ascii=False)
            results: list[ProviderResult] = []
            results.append(self._make_result("JWT Payload", "Click to copy decoded JSON", pretty))
            for key, value in payload.items():
                display_val = str(value)
                if key in ("exp", "iat", "nbf") and isinstance(value, (int, float)):
                    try:
                        dt = datetime.fromtimestamp(value, tz=timezone.utc)
                        display_val = f"{value} ({dt.strftime('%Y-%m-%d %H:%M:%S UTC')})"
                    except Exception:
                        pass
                results.append(self._make_result(f"{key}: {display_val}", "Click to copy value", str(value)))
            return results
        except Exception:
            return [self._make_result("Failed to decode JWT", "Make sure the token is valid", "")]

    def _lorem_results(self, arg: str) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        counts = [1, 2, 3, 5]
        for n in counts:
            text = self._generate_lorem(n)
            label = f"{n} paragraph{'s' if n > 1 else ''}"
            desc = text[:80] + "..." if len(text) > 80 else text
            results.append(self._make_result(label, desc, text))
        word_counts = [10, 25, 50]
        for n in word_counts:
            words = " ".join(random.choices(_LOREM_WORDS, k=n))
            words = words[0].upper() + words[1:] + "."
            results.append(self._make_result(f"{n} words", words[:80] + "..." if len(words) > 80 else words, words))
        return results

    def _generate_lorem(self, paragraphs: int) -> str:
        paras: list[str] = []
        for _ in range(paragraphs):
            sentence_count = random.randint(4, 8)
            sentences: list[str] = []
            for _ in range(sentence_count):
                length = random.randint(6, 15)
                words = " ".join(random.choices(_LOREM_WORDS, k=length))
                words = words[0].upper() + words[1:] + "."
                sentences.append(words)
            paras.append(" ".join(sentences))
        return "\n\n".join(paras)

    def _timestamp_results(self, arg: str) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        now = time.time()
        now_int = int(now)
        now_dt = datetime.fromtimestamp(now, tz=timezone.utc)

        results.append(
            self._make_result(
                f"Now: {now_int}",
                now_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                str(now_int),
            )
        )
        results.append(
            self._make_result(
                f"Now (ms): {int(now * 1000)}",
                "Millisecond timestamp",
                str(int(now * 1000)),
            )
        )
        results.append(
            self._make_result(
                f"ISO 8601: {now_dt.isoformat()}",
                "Click to copy",
                now_dt.isoformat(),
            )
        )

        if arg:
            arg_stripped = arg.strip()
            try:
                ts_val = float(arg_stripped)
                if ts_val > 1e12:
                    ts_val = ts_val / 1000
                dt = datetime.fromtimestamp(ts_val, tz=timezone.utc)
                local_dt = datetime.fromtimestamp(ts_val)
                results.append(
                    self._make_result(
                        f"UTC: {dt.strftime('%Y-%m-%d %H:%M:%S')}",
                        f"Unix {int(ts_val)} - Click to copy",
                        dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    )
                )
                results.append(
                    self._make_result(
                        f"Local: {local_dt.strftime('%Y-%m-%d %H:%M:%S')}",
                        "Local timezone - Click to copy",
                        local_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )
                results.append(
                    self._make_result(
                        f"ISO: {dt.isoformat()}",
                        "Click to copy ISO 8601",
                        dt.isoformat(),
                    )
                )
            except ValueError, OverflowError, OSError:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(arg_stripped, fmt).replace(tzinfo=timezone.utc)
                        ts_int = int(dt.timestamp())
                        results.append(
                            self._make_result(
                                f"Unix: {ts_int}",
                                f"From {arg_stripped} - Click to copy",
                                str(ts_int),
                            )
                        )
                        results.append(
                            self._make_result(
                                f"Milliseconds: {ts_int * 1000}",
                                "Click to copy",
                                str(ts_int * 1000),
                            )
                        )
                        break
                    except ValueError:
                        continue

        return results

    def _password_results(self, arg: str) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        length = 16
        if arg.isdigit():
            length = max(4, min(int(arg), 128))

        chars_all = string.ascii_letters + string.digits + string.punctuation
        chars_alpha = string.ascii_letters + string.digits
        chars_hex = string.hexdigits[:16]

        pw_full = "".join(secrets.choice(chars_all) for _ in range(length))
        pw_alpha = "".join(secrets.choice(chars_alpha) for _ in range(length))
        pw_hex = "".join(secrets.choice(chars_hex) for _ in range(length))
        passphrase = "-".join("".join(random.choices(string.ascii_lowercase, k=random.randint(4, 7))) for _ in range(4))

        results.append(self._make_result(pw_full, f"Full ({length} chars) - letters, digits, symbols", pw_full))
        results.append(self._make_result(pw_alpha, f"Alphanumeric ({length} chars) - letters, digits", pw_alpha))
        results.append(self._make_result(pw_hex, f"Hex ({length} chars)", pw_hex))
        results.append(self._make_result(passphrase, "Passphrase - 4 random words", passphrase))
        return results
