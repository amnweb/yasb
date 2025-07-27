"""
Ai Chat API client for config-driven providers (using OpenAI client only)
"""

import logging

from core.utils.widgets.ai_chat.client_helper import maybe_answer_yasb_question

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class AiChatClient:
    def __init__(self, provider_config: dict, model_name: str, max_tokens: int):
        # Import OpenAI only when an instance is created because is slow as hell
        # and we don't want to slow down YASB startup if AI widget is enabled
        try:
            from openai import OpenAI
        except ImportError:
            logging.error("openai package is required for AiChatClient")
            return
        self.OpenAI = OpenAI
        self.provider_config = provider_config
        self.provider = provider_config["provider"]
        self.api_endpoint = provider_config.get("api_endpoint")
        self.credential = provider_config.get("credential")
        self.model = model_name
        self.max_tokens = max_tokens if max_tokens > 0 else None
        self.response_content_path = provider_config.get("response_content_path", ["choices", 0, "message", "content"])
        self.base_url = self.api_endpoint.rstrip("/")
        self.api_key = self.credential or "ollama"
        self.client = self.OpenAI(base_url=self.base_url, api_key=self.api_key)
        self._cancelled = False
        self._response = None

    def stop(self):
        """
        Stop any ongoing chat request and clean up the response.
        """
        self._cancelled = True
        if self._response is not None:
            try:
                self._response.close()
            except Exception:
                pass
            self._response = None

    def chat(self, messages: list, temperature: float, top_p: float):
        self._cancelled = False
        # Check if the last message is a YASB-specific question
        answer = maybe_answer_yasb_question(messages)
        if answer is not None:
            yield answer
            return

        try:
            self._response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                logprobs=False,
                temperature=temperature,
                top_p=top_p,
                max_tokens=self.max_tokens,
                timeout=20,
            )
            response = self._response
            chunk_buffer = ""
            chunk_count = 0

            for chunk in response:
                if self._cancelled:
                    break
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                content = getattr(choice.delta, "content", None)
                if content:
                    chunk_buffer += content
                    chunk_count += 1
                    # Send buffered content every 50 chunks
                    if chunk_count >= 50:
                        yield chunk_buffer
                        chunk_buffer = ""
                        chunk_count = 0
                if getattr(choice, "finish_reason", None) == "stop":
                    break
            # Send any remaining buffered content at the end
            if chunk_buffer:
                yield chunk_buffer

            self._response = None

        except Exception as e:
            self._response = None

            err_str = str(e)
            if "401" in err_str or "invalid_api_key" in err_str or "Incorrect API key" in err_str:
                friendly = "Authentication failed: Please check your API key."
            elif "429" in err_str or "rate limit" in err_str.lower():
                friendly = "Rate limit exceeded: Please wait and try again."
            elif "timeout" in err_str.lower():
                friendly = "Request timed out: Please try again."
            else:
                friendly = None
            msg = f"[Error: {friendly}]" if friendly else f"[Error: {err_str}]"
            yield msg
