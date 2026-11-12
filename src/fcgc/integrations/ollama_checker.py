"""Opt-in Ollama JSON-schema checking over an explicitly configured endpoint."""

import ipaddress
import json
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from fcgc.checking.compliance_checker import CanonicalChecker, CheckerUnavailable
from fcgc.schemas.checking import ModelFindings


class OllamaMetadata(BaseModel):
    """Validate fields consumed by the adapter; unused provider fields may evolve."""

    model_config = ConfigDict(extra="ignore")
    remote_host: StrictStr | None = None
    remote_model: StrictStr | None = None
    details: dict | None = None
    model_info: dict | None = None


class OllamaMessage(BaseModel):
    content: StrictStr


class OllamaResponse(BaseModel):
    done: bool = Field(strict=True)
    model: StrictStr | None = None
    message: OllamaMessage
    prompt_eval_count: StrictInt | None = Field(default=None, ge=0)
    eval_count: StrictInt | None = Field(default=None, ge=0)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Checker redirects are disabled")


class LocalLLMChecker(CanonicalChecker):
    provider = "ollama"

    def __init__(
        self,
        model,
        *,
        endpoint="http://127.0.0.1:11434",
        allow_network=False,
        allow_remote=False,
        timeout=30.0,
        settings=None,
    ):
        super().__init__(settings)
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.allow_network = allow_network
        self.allow_remote = allow_remote
        self.timeout = timeout
        parsed = urlsplit(self.endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Use an Ollama origin URL without credentials or path")
        try:
            loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            loopback = parsed.hostname == "localhost"
        if not loopback and not allow_remote:
            raise ValueError("Non-loopback Ollama requires allow_remote=true")
        if not model:
            raise ValueError("Configure the exact local model identifier")
        if timeout <= 0:
            raise ValueError("Checker timeout must be positive")

    def post(self, path, payload):
        request = Request(
            self.endpoint + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(
                request, timeout=self.timeout
            ) as response:
                data = response.read(8_000_001)
                if len(data) > 8_000_000:
                    raise ValueError("Checker response exceeds local byte limit")
                return json.loads(data)
        except OSError as exc:
            raise CheckerUnavailable(str(exc)) from exc

    def predict(self, task, prompt):
        if not self.allow_network:
            raise CheckerUnavailable("Ollama disabled: set allow_network=true explicitly")
        shown = OllamaMetadata.model_validate(self.post("/api/show", {"model": self.model}))
        if not self.allow_remote and (
            shown.remote_host or shown.remote_model or self.model.endswith(":cloud")
        ):
            raise CheckerUnavailable("Remote-backed models require allow_remote=true")
        details = {"details": shown.details, "model_info": shown.model_info}
        response = OllamaResponse.model_validate(
            self.post(
                "/api/chat",
                {
                    "model": self.model,
                    "stream": False,
                    "format": ModelFindings.model_json_schema(),
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {
                        "temperature": self.settings.temperature,
                        "seed": self.settings.seed,
                        "num_predict": self.settings.max_output_tokens,
                        "top_p": self.settings.top_p,
                    },
                },
            )
        )
        if response.done is not True:
            raise ValueError("Incomplete Ollama generation")
        details["response_model"] = response.model
        prediction = ModelFindings.model_validate_json(response.message.content)
        return (
            prediction,
            json.dumps(details, sort_keys=True),
            response.prompt_eval_count,
            response.eval_count,
        )
