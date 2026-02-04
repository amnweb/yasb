"""
Copilot client wrapper for YASB AI Chat widget.
"""

import asyncio
import base64
import logging
import os
import queue
import tempfile
import threading
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable

from core.utils.widgets.ai_chat.constants import (
    BYTES_PER_KB,
    DEFAULT_ALLOWED_PERMISSION_KINDS,
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_TIMEOUT_SECONDS,
    FORMAT_TO_EXT,
    FORMAT_TO_MIME,
    MESSAGE_QUEUE_TIMEOUT_SECONDS,
)
from core.utils.widgets.ai_chat.copilot_server import copilot_cli_server, register_client, unregister_client
from settings import DEBUG

try:
    from copilot import CopilotClient
except ImportError:
    CopilotClient = None


def _get_copilot_cli_url(provider_config: dict | None) -> str | None:
    if not provider_config:
        return None
    cli_url = provider_config.get("copilot_cli_url")
    if isinstance(cli_url, str) and cli_url.strip():
        return cli_url.strip()
    return None


def _build_copilot_client_options(provider_config: dict | None) -> dict[str, Any]:
    cli_url = copilot_cli_server(_get_copilot_cli_url(provider_config))
    if not cli_url:
        return {}
    return {"cli_url": cli_url}


def _run_async(coro_factory):
    def _make_coro():
        return coro_factory() if callable(coro_factory) else coro_factory

    try:
        return asyncio.run(_make_coro())
    except RuntimeError:
        # If an event loop is already running, execute in a dedicated thread.
        result_queue: queue.Queue = queue.Queue()

        def _thread_runner():
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                result_queue.put(loop.run_until_complete(_make_coro()))
            except Exception as exc:
                result_queue.put(exc)
            finally:
                loop.close()

        thread = threading.Thread(target=_thread_runner, daemon=True)
        thread.start()
        result = result_queue.get()
        if isinstance(result, Exception):
            logging.error("Async operation failed: %s", result)
            return None
        return result


def _normalize_models(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []

    if is_dataclass(raw):
        raw = asdict(raw)

    if not isinstance(raw, list):
        return []

    items: list[dict[str, Any]] = []
    for item in raw:
        if is_dataclass(item):
            item = asdict(item)

        if not isinstance(item, dict):
            continue

        model_id = item.get("id")
        if not model_id:
            continue

        display_name = item.get("name") or model_id
        billing = item.get("billing") or {}
        multiplier = billing.get("multiplier")
        is_premium = billing.get("is_premium")

        capabilities = item.get("capabilities") or {}
        supports = capabilities.get("supports") or {}
        limits = capabilities.get("limits") or {}
        vision = limits.get("vision") or {}

        supports_vision = supports.get("vision", False)
        max_prompt_image_size = vision.get("max_prompt_image_size")
        max_image_kb = int(max_prompt_image_size / BYTES_PER_KB) if max_prompt_image_size else 0

        items.append(
            {
                "name": model_id,
                "label": display_name,
                "multiplier": multiplier,
                "is_premium": is_premium,
                "supports_vision": supports_vision,
                "max_image_size": max_image_kb,
            }
        )

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in items:
        name = item.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(item)
    return normalized


def list_copilot_models(provider_config: dict | None = None) -> list[dict[str, Any]]:
    if CopilotClient is None:
        logging.error("copilot-sdk package is required for Copilot provider")
        return []

    async def _list() -> list[dict[str, Any]]:
        client = CopilotClient(_build_copilot_client_options(provider_config))
        await client.start()
        auth_status = await client.get_auth_status()
        if not getattr(auth_status, "isAuthenticated", False):
            await client.stop()
            logging.error("Copilot CLI is not authenticated. Run `copilot` to sign in.")
            return []
        try:
            models = await client.list_models()
        except Exception as exc:
            logging.warning("Copilot models unavailable: %s", exc)
            await client.stop()
            return []
        await client.stop()
        return _normalize_models(models)

    try:
        models = _run_async(_list)
        if not models:
            return []
        if DEBUG:
            logging.debug(
                "Available Copilot models: %s",
                [item.get("name") for item in models],
            )
        return _sort_models_free_first(models)
    except Exception as exc:
        logging.exception(f"Failed to list Copilot models: {exc}")
        return []


def _sort_models_free_first(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _is_free(item: dict[str, Any]) -> bool:
        if item.get("multiplier") == 0:
            return True
        if item.get("is_premium") is False:
            return True
        name = (item.get("name") or "").lower()
        label = (item.get("label") or "").lower()
        return "free" in name or "free" in label

    return sorted(models, key=lambda item: (not _is_free(item), item.get("label") or item.get("name") or ""))


class CopilotAiChatClient:
    def __init__(self, provider_config: dict, model_name: str):
        self.provider_config = provider_config
        self.provider = provider_config.get("provider", "Copilot")
        self.model = model_name
        self._cancelled = False
        self._session = None
        self._client = None
        self._temp_files: list[str] = []

        self._loop = None
        self._loop_thread = None
        self._loop_ready = threading.Event()
        self._request_lock = threading.Lock()
        self._session_lock = threading.Lock()
        self._active_queue: queue.Queue | None = None
        self._active_done: threading.Event | None = None
        self._active_idle: asyncio.Event | None = None
        self._session_handler_registered = False
        self._session_system_message: str | None = None
        self._saw_delta = False
        self._had_output = False

        self._start_event_loop()
        register_client(self)

    def stop(self):
        """Abort the current request. Session remains usable for new messages."""
        self._cancelled = True
        try:
            self._run_coroutine(self._abort_session())
        except Exception as e:
            if DEBUG:
                logging.debug(f"Error aborting Copilot session: {e}")

    def close(self):
        """Destroy session and release all resources."""
        unregister_client(self)
        try:
            self._run_coroutine(self._destroy_session())
        except Exception as e:
            if DEBUG:
                logging.debug(f"Error destroying Copilot session: {e}")
        if self._loop and self._loop_thread:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._loop_thread.join(timeout=2)
            except Exception as e:
                if DEBUG:
                    logging.debug(f"Error stopping Copilot event loop: {e}")

    def chat(
        self,
        messages: list[dict[str, Any]],
    ) -> Iterable[str]:
        self._cancelled = False

        with self._request_lock:
            system_message, prompt, attachments = self._build_prompt_and_attachments(messages)

            message_queue: queue.Queue[str | None] = queue.Queue()
            done_event = threading.Event()

            future = asyncio.run_coroutine_threadsafe(
                self._chat_async(prompt, system_message, attachments, message_queue, done_event), self._loop
            )

            while not done_event.is_set() or not message_queue.empty():
                if self._cancelled:
                    break
                try:
                    item = message_queue.get(timeout=MESSAGE_QUEUE_TIMEOUT_SECONDS)
                except queue.Empty:
                    continue
                if item is None:
                    done_event.set()
                    continue
                yield item

            # Re-raise any errors so the worker can handle them
            future.result()

    def _build_prompt_and_attachments(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[str | None, str, list[dict[str, str]]]:
        system_message = None
        prompt = ""

        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content")
                break

        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    prompt = content
                elif isinstance(content, list):
                    parts = [
                        p.get("text")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text" and p.get("text")
                    ]
                    prompt = "\n".join(parts)
                break

        attachments = self._build_image_attachments(messages)
        return system_message, prompt, attachments

    def _data_url_to_temp_file(self, data_url: str) -> str | None:
        if not isinstance(data_url, str) or not data_url.startswith("data:"):
            return None
        try:
            header, b64_data = data_url.split(",", 1)
        except ValueError:
            return None

        if ";base64" not in header:
            return None

        mime = header[5:].split(";", 1)[0]
        mime_to_ext = {value: f".{FORMAT_TO_EXT[key]}" for key, value in FORMAT_TO_MIME.items()}
        ext = mime_to_ext.get(mime, ".png")

        try:
            raw = base64.b64decode(b64_data)
        except Exception:
            return None

        fd, path = tempfile.mkstemp(prefix="yasb_copilot_", suffix=ext)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)

        self._temp_files.append(path)
        return path

    async def _chat_async(
        self,
        prompt: str,
        system_message: str | None,
        attachments: list[dict[str, str]],
        message_queue: queue.Queue[str | None],
        done_event: threading.Event,
    ) -> None:
        await self._ensure_session(system_message)
        if not self._session:
            logging.error("Copilot session is not available")
            message_queue.put(None)
            done_event.set()
            raise RuntimeError("Copilot session is not available")

        self._active_queue = message_queue
        self._active_done = done_event
        self._active_idle = asyncio.Event()
        self._saw_delta = False
        self._had_output = False

        payload: dict[str, Any] = {"prompt": prompt}
        if attachments:
            payload["attachments"] = attachments

        try:
            await self._session.send(payload)
            # Wait with timeout to prevent hanging forever
            try:
                await asyncio.wait_for(self._active_idle.wait(), timeout=DEFAULT_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logging.warning(f"Copilot request timed out after {DEFAULT_TIMEOUT_SECONDS} seconds")
                await self._abort_session()
                raise TimeoutError("Request timed out")
            if not self._had_output:
                logging.warning("No response from Copilot")
                raise RuntimeError("No response from Copilot")
        finally:
            self._active_queue = None
            self._active_done = None
            self._active_idle = None
            message_queue.put(None)
            done_event.set()

    def _build_image_attachments(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        attachments: list[dict[str, str]] = []
        last_user = next((msg for msg in reversed(messages) if msg.get("role") == "user"), None)

        for att in (last_user.get("attachments") or []) if last_user else []:
            if not att.get("is_image"):
                continue

            # If image was compressed use the processed base64 version
            # Otherwise use original file path if it exists
            if not att.get("compressed"):
                path = att.get("path")
                if path and os.path.exists(path):
                    attachments.append({"type": "file", "path": path})
                    continue

            # Use temp file from base64 (for compressed images or clipboard pastes)
            image_url = att.get("image_url")
            temp_path = self._data_url_to_temp_file(image_url) if image_url else None
            if temp_path:
                attachments.append({"type": "file", "path": temp_path})
                continue

            if DEBUG:
                logging.debug(f"Copilot skipped image attachment (no file): {att.get('name')}")

        return attachments

    def _start_event_loop(self):
        if self._loop_thread and self._loop:
            return

        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._loop_ready.set()
            loop.run_forever()

        self._loop_thread = threading.Thread(target=_runner, daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5)

    def _run_coroutine(self, coro):
        if not self._loop:
            self._start_event_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    async def _ensure_session(self, system_message: str | None) -> None:
        with self._session_lock:
            if not self._client or not self._session:
                await self._create_session(system_message)
                return

            if self._session_system_message != system_message:
                await self._destroy_session()
                await self._create_session(system_message)

    async def _create_session(self, system_message: str | None) -> None:
        if CopilotClient is None:
            logging.error("copilot-sdk package is required for Copilot provider")
            raise RuntimeError("copilot-sdk package is required")

        client = CopilotClient(_build_copilot_client_options(self.provider_config))
        try:
            await client.start()
            auth_status = await client.get_auth_status()
            if not getattr(auth_status, "isAuthenticated", False):
                logging.error("Copilot CLI is not authenticated. Run `copilot` to sign in.")
                await client.stop()
                self._client = None
                self._session = None
                return
        except FileNotFoundError:
            logging.error("Copilot CLI not found. Please install GitHub Copilot CLI.")
            raise RuntimeError("Copilot CLI not found")
        except ConnectionError as e:
            logging.error(f"Could not connect to Copilot CLI server: {e}")
            raise RuntimeError("Could not connect to Copilot CLI server")
        except Exception as e:
            logging.error(f"Failed to start Copilot client: {e}")
            raise RuntimeError("Failed to start Copilot client")

        self._client = client

        session_args: dict[str, Any] = {
            "model": self.model,
            "streaming": True,
            "on_permission_request": self._handle_permission_request,
            "available_tools": list(DEFAULT_ALLOWED_TOOLS),
        }
        if system_message:
            session_args["system_message"] = {"mode": "append", "content": system_message}

        try:
            self._session = await client.create_session(session_args)
        except Exception as e:
            logging.error(f"Failed to create Copilot session: {e}")
            # Clean up client if session creation fails
            try:
                await client.stop()
            except Exception:
                pass
            self._client = None
            raise

        self._session_system_message = system_message

        if not self._session_handler_registered:
            self._session.on(self._handle_event)
            self._session_handler_registered = True

    async def _destroy_session(self) -> None:
        if self._session:
            try:
                await self._session.destroy()
            except Exception:
                pass
        if self._client:
            try:
                await self._client.stop()
            except Exception:
                pass
        self._session = None
        self._client = None
        self._session_handler_registered = False
        for path in self._temp_files:
            try:
                os.unlink(path)
            except Exception:
                pass
        self._temp_files.clear()

    async def _abort_session(self) -> None:
        if self._session and hasattr(self._session, "abort"):
            result = self._session.abort()
            if asyncio.iscoroutine(result):
                await result

    def _handle_permission_request(self, request: dict, _invocation: dict) -> dict:
        try:
            kind = request.get("kind")
            if kind in DEFAULT_ALLOWED_PERMISSION_KINDS:
                return {"kind": "approved"}
        except Exception:
            pass

        return {"kind": "denied-by-rules"}

    def _handle_event(self, event: Any) -> None:
        event_type = None
        if hasattr(event, "type"):
            event_type = event.type.value if hasattr(event.type, "value") else event.type
        elif isinstance(event, dict):
            event_type = event.get("type")

        # Always process session.idle to unblock waiting coroutines, even when cancelled
        if event_type == "session.idle":
            if self._active_idle is not None:
                self._active_idle.set()
            if self._active_done is not None:
                self._active_done.set()
            return

        # Skip other events when cancelled
        if self._cancelled:
            return

        if event_type in {"assistant.message_delta", "assistant.message"}:
            data = getattr(event, "data", None)
            content = (
                getattr(data, "delta_content", None)
                if event_type == "assistant.message_delta"
                else getattr(data, "content", None)
            )
            if content and self._active_queue is not None:
                if event_type == "assistant.message_delta":
                    self._saw_delta = True
                elif self._saw_delta:
                    return
                self._had_output = True
                self._active_queue.put(content)
