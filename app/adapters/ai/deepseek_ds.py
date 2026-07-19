"""Minimal DeepSeek chat-completion client without tool or code execution support."""

import json
from urllib.request import Request, urlopen


class DeepSeekCompletion:
    def __init__(self, api_key: str, endpoint: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._timeout_seconds = timeout_seconds

    def __call__(self, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload["choices"][0]["message"]["content"])
