from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from app.integrations.portal_unico import (
    DuimpIdentifier,
    PortalUnicoCredentials,
    PortalUnicoDuimpGateway,
    PortalUnicoResponse,
)


@dataclass
class RecordedRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    query: Mapping[str, Any] | None


class FakeTransport:
    def __init__(self, responses: list[PortalUnicoResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[RecordedRequest] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        query: Mapping[str, Any] | None = None,
        timeout_seconds: float = 30,
    ) -> PortalUnicoResponse:
        self.requests.append(
            RecordedRequest(method, url, dict(headers or {}), query)
        )
        return self.responses.pop(0)


def response(payload: Any, csrf: str | None = None, **headers: str):
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return PortalUnicoResponse(200, headers, payload)


@pytest.mark.parametrize(
    ("raw", "compact", "formatted"),
    [
        ("26BR0000000000-1", "26BR00000000001", "26BR0000000000-1"),
        (" 26br00000000001 ", "26BR00000000001", "26BR0000000000-1"),
    ],
)
def test_duimp_identifier_accepts_operator_and_api_formats(raw, compact, formatted):
    identifier = DuimpIdentifier.parse(raw)
    assert identifier.compact == compact
    assert identifier.formatted == formatted


@pytest.mark.parametrize(
    "raw", ["", "26BR0001106747", "26BR0001106747-X", "2026BR00000000001"]
)
def test_duimp_identifier_rejects_invalid_values(raw):
    with pytest.raises(ValueError, match="Número da DUIMP inválido"):
        DuimpIdentifier.parse(raw)


def test_gateway_authenticates_gets_current_version_and_paginates_items():
    pages = [
        [{"identificacao": {"numeroItem": number}} for number in range(1, 101)],
        [{"identificacao": {"numeroItem": number}} for number in range(101, 201)],
        [{"identificacao": {"numeroItem": number}} for number in range(201, 206)],
    ]
    transport = FakeTransport(
        [
            response({}, **{"Set-Token": "jwt-1", "X-CSRF-Token": "csrf-1"}),
            response({"versao": "1"}, csrf="csrf-2"),
            response({"quantidadeItens": 205}, csrf="csrf-3"),
            response(pages[0], csrf="csrf-4"),
            response(pages[1], csrf="csrf-5"),
            response(pages[2], csrf="csrf-6"),
        ]
    )
    gateway = PortalUnicoDuimpGateway(
        credentials=PortalUnicoCredentials("client-id", "client-secret"),
        environment="production",
        transport=transport,
    )

    result = gateway.fetch_duimp(duimp_number="26BR0000000000-1")

    assert result["numero"] == "26BR0000000000-1"
    assert result["numeroApi"] == "26BR00000000001"
    assert result["versao"] == "1"
    assert len(result["itens"]) == 205

    auth = transport.requests[0]
    assert auth.url.endswith("/portal/api/autenticar/chave-acesso")
    assert auth.headers == {
        "Client-Id": "client-id",
        "Client-Secret": "client-secret",
        "Role-Type": "IMPEXP",
    }
    assert transport.requests[1].url.endswith(
        "/duimp-api/api/ext/duimp/26BR00000000001/versoes"
    )
    assert transport.requests[2].url.endswith(
        "/duimp-api/api/ext/duimp/26BR00000000001/1"
    )
    assert [request.query["inicial"] for request in transport.requests[3:]] == [
        1,
        101,
        201,
    ]
    assert [request.headers["X-CSRF-Token"] for request in transport.requests[1:]] == [
        "csrf-1",
        "csrf-2",
        "csrf-3",
        "csrf-4",
        "csrf-5",
    ]


def test_gateway_rejects_item_count_mismatch():
    transport = FakeTransport(
        [
            response({}, **{"Set-Token": "jwt", "X-CSRF-Token": "csrf"}),
            response({"versao": "1"}),
            response({"quantidadeItens": 2}),
            response([{"identificacao": {"numeroItem": 1}}]),
        ]
    )
    gateway = PortalUnicoDuimpGateway(
        credentials=PortalUnicoCredentials("id", "secret"),
        environment="homologation",
        transport=transport,
    )

    with pytest.raises(Exception, match="informa 2 itens, mas a API retornou 1"):
        gateway.fetch_duimp(duimp_number="26BR00000000001")
