from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class NfeIssuanceStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    XML_GENERATED = "xml_generated"
    XSD_VALIDATED = "xsd_validated"
    VALIDATION_FAILED = "validation_failed"
    SIGNED = "signed"
    SUBMISSION_PENDING = "submission_pending"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"
    DENIED = "denied"
    CANCELLATION_PENDING = "cancellation_pending"
    CANCELLED = "cancelled"
    FAILED = "failed"


class NfeIssuanceStateError(ValueError):
    pass


class NfeIdempotencyConflict(ValueError):
    pass


@dataclass(frozen=True)
class NfeStateTransition:
    previous: NfeIssuanceStatus
    current: NfeIssuanceStatus


class NfeIssuanceStateMachine:
    """Regras puras para impedir saltos e reabertura indevida da emissão."""

    ALLOWED: dict[NfeIssuanceStatus, frozenset[NfeIssuanceStatus]] = {
        NfeIssuanceStatus.DRAFT: frozenset(
            {NfeIssuanceStatus.VALIDATED, NfeIssuanceStatus.FAILED}
        ),
        NfeIssuanceStatus.VALIDATED: frozenset(
            {NfeIssuanceStatus.XML_GENERATED, NfeIssuanceStatus.FAILED}
        ),
        NfeIssuanceStatus.XML_GENERATED: frozenset(
            {
                NfeIssuanceStatus.XSD_VALIDATED,
                NfeIssuanceStatus.VALIDATION_FAILED,
                NfeIssuanceStatus.FAILED,
            }
        ),
        NfeIssuanceStatus.VALIDATION_FAILED: frozenset(
            {NfeIssuanceStatus.DRAFT}
        ),
        NfeIssuanceStatus.XSD_VALIDATED: frozenset(
            {NfeIssuanceStatus.SIGNED, NfeIssuanceStatus.FAILED}
        ),
        NfeIssuanceStatus.SIGNED: frozenset(
            {NfeIssuanceStatus.SUBMISSION_PENDING, NfeIssuanceStatus.FAILED}
        ),
        NfeIssuanceStatus.SUBMISSION_PENDING: frozenset(
            {NfeIssuanceStatus.SUBMITTED, NfeIssuanceStatus.FAILED}
        ),
        NfeIssuanceStatus.SUBMITTED: frozenset(
            {
                NfeIssuanceStatus.PROCESSING,
                NfeIssuanceStatus.AUTHORIZED,
                NfeIssuanceStatus.REJECTED,
                NfeIssuanceStatus.DENIED,
                NfeIssuanceStatus.FAILED,
            }
        ),
        NfeIssuanceStatus.PROCESSING: frozenset(
            {
                NfeIssuanceStatus.AUTHORIZED,
                NfeIssuanceStatus.REJECTED,
                NfeIssuanceStatus.DENIED,
                NfeIssuanceStatus.FAILED,
            }
        ),
        NfeIssuanceStatus.REJECTED: frozenset({NfeIssuanceStatus.DRAFT}),
        NfeIssuanceStatus.AUTHORIZED: frozenset(
            {NfeIssuanceStatus.CANCELLATION_PENDING}
        ),
        NfeIssuanceStatus.CANCELLATION_PENDING: frozenset(
            {NfeIssuanceStatus.CANCELLED, NfeIssuanceStatus.AUTHORIZED}
        ),
        NfeIssuanceStatus.DENIED: frozenset(),
        NfeIssuanceStatus.CANCELLED: frozenset(),
        NfeIssuanceStatus.FAILED: frozenset(),
    }

    TERMINAL = frozenset(
        {
            NfeIssuanceStatus.DENIED,
            NfeIssuanceStatus.CANCELLED,
            NfeIssuanceStatus.FAILED,
        }
    )

    def transition(
        self,
        current: NfeIssuanceStatus | str,
        target: NfeIssuanceStatus | str,
    ) -> NfeStateTransition:
        previous = self._status(current)
        desired = self._status(target)
        if desired not in self.ALLOWED[previous]:
            raise NfeIssuanceStateError(
                f"Transição de emissão inválida: {previous.value} -> {desired.value}."
            )
        return NfeStateTransition(previous=previous, current=desired)

    @staticmethod
    def _status(value: NfeIssuanceStatus | str) -> NfeIssuanceStatus:
        try:
            return (
                value
                if isinstance(value, NfeIssuanceStatus)
                else NfeIssuanceStatus(str(value))
            )
        except ValueError as exc:
            raise NfeIssuanceStateError(
                f"Estado de emissão desconhecido: {value}."
            ) from exc


class NfeIdempotency:
    """Garante que a mesma chave nunca represente solicitações diferentes."""

    @staticmethod
    def request_hash(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def assert_replay_matches(
        self,
        *,
        idempotency_key: str,
        stored_request_hash: str,
        payload: dict[str, Any],
    ) -> None:
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("A chave de idempotência é obrigatória.")
        if len(key) > 128:
            raise ValueError("A chave de idempotência deve ter no máximo 128 caracteres.")

        incoming_hash = self.request_hash(payload)
        if incoming_hash != stored_request_hash:
            raise NfeIdempotencyConflict(
                "A chave de idempotência já foi usada com outro conteúdo."
            )
