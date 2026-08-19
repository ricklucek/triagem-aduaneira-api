import pytest

from app.services.nfe_issuance_state import (
    NfeIdempotency,
    NfeIdempotencyConflict,
    NfeIssuanceStateError,
    NfeIssuanceStateMachine,
    NfeIssuanceStatus,
)


def test_happy_path_reaches_authorized_state():
    machine = NfeIssuanceStateMachine()
    current = NfeIssuanceStatus.DRAFT
    for target in [
        NfeIssuanceStatus.VALIDATED,
        NfeIssuanceStatus.XML_GENERATED,
        NfeIssuanceStatus.XSD_VALIDATED,
        NfeIssuanceStatus.SIGNED,
        NfeIssuanceStatus.SUBMISSION_PENDING,
        NfeIssuanceStatus.SUBMITTED,
        NfeIssuanceStatus.PROCESSING,
        NfeIssuanceStatus.AUTHORIZED,
    ]:
        current = machine.transition(current, target).current

    assert current is NfeIssuanceStatus.AUTHORIZED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "signed"),
        ("xml_generated", "submitted"),
        ("authorized", "draft"),
        ("denied", "submitted"),
        ("cancelled", "authorized"),
        ("failed", "draft"),
    ],
)
def test_rejects_unsafe_state_jumps(current, target):
    with pytest.raises(NfeIssuanceStateError, match="Transição de emissão inválida"):
        NfeIssuanceStateMachine().transition(current, target)


def test_rejected_document_can_be_corrected_without_reusing_an_authorized_number():
    transition = NfeIssuanceStateMachine().transition("rejected", "draft")
    assert transition.previous is NfeIssuanceStatus.REJECTED
    assert transition.current is NfeIssuanceStatus.DRAFT


def test_authorized_document_can_only_enter_cancellation_flow():
    transition = NfeIssuanceStateMachine().transition(
        "authorized", "cancellation_pending"
    )
    assert transition.current is NfeIssuanceStatus.CANCELLATION_PENDING


def test_idempotency_hash_is_stable_for_equivalent_json():
    first = {"series": "1", "number": 10, "items": [{"ncm": "87087090"}]}
    second = {"items": [{"ncm": "87087090"}], "number": 10, "series": "1"}

    assert NfeIdempotency.request_hash(first) == NfeIdempotency.request_hash(second)


def test_idempotency_replay_rejects_different_request():
    original = {"series": "1", "number": 10}
    stored_hash = NfeIdempotency.request_hash(original)

    with pytest.raises(NfeIdempotencyConflict, match="outro conteúdo"):
        NfeIdempotency().assert_replay_matches(
            idempotency_key="emit-123",
            stored_request_hash=stored_hash,
            payload={"series": "1", "number": 11},
        )


def test_idempotency_replay_accepts_same_request():
    payload = {"series": "1", "number": 10}
    NfeIdempotency().assert_replay_matches(
        idempotency_key="emit-123",
        stored_request_hash=NfeIdempotency.request_hash(payload),
        payload=payload,
    )
