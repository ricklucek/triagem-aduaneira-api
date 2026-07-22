from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PortalUnicoIntegrationError(RuntimeError):
    """Falha de configuração, transporte ou contrato do Portal Único."""


class PortalUnicoApiError(PortalUnicoIntegrationError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True)
class DuimpIdentifier:
    """Representa o número da DUIMP nas formas usada pela API e pelo operador."""

    compact: str

    _PATTERN = re.compile(r"^[0-9]{2}BR[0-9]{11}$")

    @classmethod
    def parse(cls, value: str) -> "DuimpIdentifier":
        raw = str(value or "").strip().upper()
        compact = re.sub(r"[\s-]", "", raw)
        if not cls._PATTERN.fullmatch(compact):
            raise ValueError(
                "Número da DUIMP inválido. Use o formato 26BR0000000000-1 "
                "ou 26BR00000000001."
            )
        return cls(compact=compact)

    @property
    def formatted(self) -> str:
        return f"{self.compact[:-1]}-{self.compact[-1]}"


@dataclass(frozen=True)
class PortalUnicoCredentials:
    client_id: str
    client_secret: str
    role_type: str = "IMPEXP"

    def __post_init__(self) -> None:
        if not self.client_id or not self.client_secret:
            raise PortalUnicoIntegrationError(
                "Client-Id e Client-Secret do Portal Único são obrigatórios."
            )
        if self.role_type != "IMPEXP":
            raise PortalUnicoIntegrationError(
                "A consulta de DUIMP por interveniente privado requer Role-Type IMPEXP."
            )


class PortalCredentialResolver(Protocol):
    def resolve(self, credentials_ref: str, *, role_type: str) -> PortalUnicoCredentials:
        ...


class EnvironmentPortalCredentialResolver:
    """Resolve credenciais sem armazená-las no banco.

    ``credentials_ref=env:CLIENTE_ACME_PORTAL`` procura as variáveis
    ``CLIENTE_ACME_PORTAL_CLIENT_ID`` e ``CLIENTE_ACME_PORTAL_CLIENT_SECRET``.
    Em produção, este resolver pode ser substituído por Secret Manager/Vault.
    """

    def resolve(self, credentials_ref: str, *, role_type: str) -> PortalUnicoCredentials:
        prefix = str(credentials_ref or "")
        if not prefix.startswith("env:"):
            raise PortalUnicoIntegrationError(
                "credentials_ref inválido. Para o resolver atual use env:NOME_DO_SEGREDO."
            )

        env_prefix = prefix.removeprefix("env:").strip()
        if not env_prefix or not re.fullmatch(r"[A-Z][A-Z0-9_]*", env_prefix):
            raise PortalUnicoIntegrationError(
                "O prefixo de credentials_ref deve conter apenas letras maiúsculas, "
                "números e sublinhado."
            )

        return PortalUnicoCredentials(
            client_id=os.getenv(f"{env_prefix}_CLIENT_ID", ""),
            client_secret=os.getenv(f"{env_prefix}_CLIENT_SECRET", ""),
            role_type=role_type,
        )


@dataclass(frozen=True)
class PortalUnicoResponse:
    status_code: int
    headers: Mapping[str, str]
    payload: Any

    def header(self, name: str) -> str | None:
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return None


class JsonTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
        timeout_seconds: float = 30,
    ) -> PortalUnicoResponse:
        ...


class UrllibJsonTransport:
    """Transporte JSON mínimo, sem dependência externa e injetável nos testes."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
        timeout_seconds: float = 30,
    ) -> PortalUnicoResponse:
        if query:
            url = f"{url}?{urlencode(query)}"

        request_headers = {
            "Accept": "application/json",
            "User-Agent": "triagem-aduaneira-api/1.0",
            **dict(headers or {}),
        }
        data = b"" if method.upper() in {"POST", "PUT", "PATCH"} else None
        request = Request(url, data=data, headers=request_headers, method=method.upper())

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
                payload = self._decode_json(body)
                return PortalUnicoResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    payload=payload,
                )
        except HTTPError as exc:
            payload = self._decode_json(exc.read())
            error_code, message = self._api_error_details(payload)
            raise PortalUnicoApiError(
                message or f"Portal Único retornou HTTP {exc.code}.",
                status_code=exc.code,
                error_code=error_code,
            ) from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise PortalUnicoIntegrationError(
                "Não foi possível conectar ao Portal Único."
            ) from exc

    @staticmethod
    def _decode_json(body: bytes) -> Any:
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PortalUnicoIntegrationError(
                "O Portal Único retornou uma resposta que não é JSON válido."
            ) from exc

    @staticmethod
    def _api_error_details(payload: Any) -> tuple[str | None, str | None]:
        if not isinstance(payload, dict):
            return None, None
        code = payload.get("code") or payload.get("codigo") or payload.get("errorCode")
        message = (
            payload.get("message")
            or payload.get("mensagem")
            or payload.get("detail")
            or payload.get("error")
        )
        return (str(code) if code else None, str(message) if message else None)


class PortalUnicoDuimpGateway:
    AUTH_PATH = "/portal/api/autenticar/chave-acesso"
    DUIMP_BASE_PATH = "/duimp-api/api/ext"
    ENVIRONMENT_HOSTS = {
        "homologation": "https://val.portalunico.siscomex.gov.br",
        "validation": "https://val.portalunico.siscomex.gov.br",
        "production": "https://portalunico.siscomex.gov.br",
    }

    def __init__(
        self,
        *,
        credentials: PortalUnicoCredentials,
        environment: str,
        transport: JsonTransport | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 30,
        page_size: int = 100,
    ) -> None:
        if environment not in self.ENVIRONMENT_HOSTS:
            raise PortalUnicoIntegrationError(
                "Ambiente do Portal Único deve ser validation/homologation ou production."
            )
        if not 1 <= page_size <= 100:
            raise ValueError("page_size deve estar entre 1 e 100.")

        self.credentials = credentials
        self.environment = environment
        self.transport = transport or UrllibJsonTransport()
        self.base_url = (base_url or self.ENVIRONMENT_HOSTS[environment]).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.page_size = page_size
        self._authorization: str | None = None
        self._csrf_token: str | None = None

    def authenticate(self) -> None:
        response = self.transport.request(
            "POST",
            f"{self.base_url}{self.AUTH_PATH}",
            headers={
                "Client-Id": self.credentials.client_id,
                "Client-Secret": self.credentials.client_secret,
                "Role-Type": self.credentials.role_type,
            },
            timeout_seconds=self.timeout_seconds,
        )
        authorization = response.header("Set-Token")
        csrf_token = response.header("X-CSRF-Token")
        if not authorization or not csrf_token:
            raise PortalUnicoIntegrationError(
                "Autenticação concluída sem os headers Set-Token e X-CSRF-Token."
            )
        self._authorization = authorization
        self._csrf_token = csrf_token

    def fetch_duimp(
        self,
        *,
        duimp_number: str,
        duimp_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if duimp_payload is not None:
            raise ValueError("O gateway real não aceita duimp_payload manual.")

        identifier = DuimpIdentifier.parse(duimp_number)
        self.authenticate()

        version_payload = self._get(f"/duimp/{identifier.compact}/versoes")
        version = self._extract_version(version_payload)
        general = self._get(f"/duimp/{identifier.compact}/{version}")
        expected_items = int(general.get("quantidadeItens") or 0)
        items = self._fetch_items(identifier.compact, version, expected_items)

        if expected_items and len(items) != expected_items:
            raise PortalUnicoIntegrationError(
                f"A DUIMP informa {expected_items} itens, mas a API retornou {len(items)}."
            )

        return {
            "provider": "portal_unico",
            "numero": identifier.formatted,
            "numeroApi": identifier.compact,
            "versao": str(version),
            "dadosGerais": general,
            "itens": items,
        }

    def healthcheck(self) -> dict[str, str]:
        self.authenticate()
        return {"status": "ok", "environment": self.environment}

    def _fetch_items(
        self, compact_number: str, version: int, expected_items: int
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        initial = 1

        while True:
            page = self._get(
                f"/duimp/{compact_number}/{version}/itens",
                query={"inicial": initial, "tamanho": self.page_size},
            )
            if not isinstance(page, list):
                raise PortalUnicoIntegrationError(
                    "A consulta de itens da DUIMP não retornou uma lista."
                )
            items.extend(page)

            if not page:
                break
            if expected_items and len(items) >= expected_items:
                break
            if len(page) < self.page_size:
                break
            initial += len(page)

        return items

    def _get(self, path: str, *, query: Mapping[str, Any] | None = None) -> Any:
        if not self._authorization or not self._csrf_token:
            raise PortalUnicoIntegrationError("Sessão do Portal Único não autenticada.")

        response = self.transport.request(
            "GET",
            f"{self.base_url}{self.DUIMP_BASE_PATH}{path}",
            headers={
                "Authorization": self._authorization,
                "X-CSRF-Token": self._csrf_token,
            },
            query=query,
            timeout_seconds=self.timeout_seconds,
        )
        renewed_csrf = response.header("X-CSRF-Token")
        if renewed_csrf:
            self._csrf_token = renewed_csrf
        return response.payload

    @staticmethod
    def _extract_version(payload: Any) -> int:
        if not isinstance(payload, dict) or payload.get("versao") in (None, ""):
            raise PortalUnicoIntegrationError(
                "A consulta de versão vigente não retornou o campo versao."
            )
        try:
            version = int(payload["versao"])
        except (TypeError, ValueError) as exc:
            raise PortalUnicoIntegrationError(
                "A versão vigente retornada pelo Portal Único é inválida."
            ) from exc
        if not 1 <= version <= 9999:
            raise PortalUnicoIntegrationError(
                "A versão vigente retornada pelo Portal Único está fora do intervalo permitido."
            )
        return version
