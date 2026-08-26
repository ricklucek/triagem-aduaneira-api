from datetime import datetime

from app.extensions import db
from app.models.import_process import (
    NfeNumberSequence,
    NfeNumberSequenceStatusEnum,
)


class NfeSequenceRegressionError(ValueError):
    def __init__(self, *, requested: int, minimum: int):
        self.requested = requested
        self.minimum = minimum
        super().__init__(
            f"O número atual não pode regredir para {requested}. "
            f"O menor valor seguro é {minimum}."
        )


class NfeNumberSequenceService:
    def __init__(self, current_user):
        self.current_user = current_user

    def get_sequence_or_raise(
        self,
        *,
        client_id,
        environment: str,
        model: str,
        series: str,
    ) -> NfeNumberSequence:
        sequence = (
            NfeNumberSequence.query
            .filter(
                NfeNumberSequence.organization_id == self.current_user.organization_id,
                NfeNumberSequence.client_id == client_id,
                NfeNumberSequence.environment == environment,
                NfeNumberSequence.model == model,
                NfeNumberSequence.series == series,
                NfeNumberSequence.status == NfeNumberSequenceStatusEnum.ACTIVE.value,
            )
            .first()
        )

        if not sequence:
            raise ValueError(
                "Sequência numérica da NF-e não configurada para este importador, "
                "ambiente, modelo e série."
            )

        return sequence

    def reserve_next_number(
        self,
        *,
        client_id,
        environment: str,
        model: str = "55",
        series: str,
    ) -> int:
        """
        Reserva o próximo número da NF-e.

        Importante:
        use com db.session.begin_nested() ou dentro de uma transação.
        Em PostgreSQL, o with_for_update() bloqueia a linha até o commit,
        evitando duplicidade em chamadas simultâneas.
        """

        sequence = (
            NfeNumberSequence.query
            .filter(
                NfeNumberSequence.organization_id == self.current_user.organization_id,
                NfeNumberSequence.client_id == client_id,
                NfeNumberSequence.environment == environment,
                NfeNumberSequence.model == model,
                NfeNumberSequence.series == series,
                NfeNumberSequence.status == NfeNumberSequenceStatusEnum.ACTIVE.value,
            )
            .with_for_update()
            .first()
        )

        if not sequence:
            raise ValueError(
                "Sequência numérica da NF-e não configurada para este importador, "
                "ambiente, modelo e série."
            )

        if sequence.current_number < sequence.initial_number - 1:
            sequence.current_number = sequence.initial_number - 1

        next_number = sequence.current_number + 1

        if next_number > sequence.max_number:
            raise ValueError(
                "Sequência numérica da NF-e atingiu o número máximo permitido."
            )

        now = datetime.now()

        sequence.current_number = next_number
        sequence.last_reserved_number = next_number
        sequence.last_reserved_at = now
        sequence.updated_at = now

        return next_number
    
    def create_or_update_nfe_number_sequence(
        self,
        *,
        client_id,
        environment: str,
        model: str,
        series: str,
        current_number: int | None = None,
        initial_number: int = 1,
        max_number: int = 999999999,
        status: str = "active",
    ) -> NfeNumberSequence:
        if environment != "production":
            raise ValueError(
                "Novas sequências fiscais aceitam somente o ambiente production."
            )
        if initial_number < 1:
            raise ValueError("Número inicial da sequência deve ser maior ou igual a 1.")
        if max_number > 999999999:
            raise ValueError("Número máximo da NF-e não pode ultrapassar 999999999.")
        if max_number < initial_number:
            raise ValueError("Número máximo não pode ser menor que o número inicial.")
        if current_number is not None and current_number < 0:
            raise ValueError("Número atual da sequência não pode ser negativo.")

        sequence = (
            NfeNumberSequence.query
            .filter(
                NfeNumberSequence.organization_id == self.current_user.organization_id,
                NfeNumberSequence.client_id == client_id,
                NfeNumberSequence.environment == environment,
                NfeNumberSequence.model == model,
                NfeNumberSequence.series == series,
            )
            .with_for_update()
            .first()
        )

        now = datetime.now()
        is_new = sequence is None
        if is_new:
            sequence = NfeNumberSequence(
                organization_id=self.current_user.organization_id,
                client_id=client_id,
                environment=environment,
                model=model,
                series=series,
                created_by_user_id=self.current_user.id,
                created_at=now,
                updated_at=now,
            )
            db.session.add(sequence)

        persisted_current = 0 if is_new else int(sequence.current_number or 0)
        last_reserved = 0 if is_new else int(sequence.last_reserved_number or 0)
        minimum_safe = max(persisted_current, last_reserved, initial_number - 1)
        requested_current = minimum_safe if current_number is None else current_number
        if requested_current < minimum_safe:
            raise NfeSequenceRegressionError(
                requested=requested_current,
                minimum=minimum_safe,
            )
        if requested_current > max_number:
            raise ValueError(
                "Número atual não pode ser maior que o número máximo da sequência."
            )

        sequence.current_number = requested_current
        sequence.initial_number = initial_number
        sequence.max_number = max_number
        sequence.status = status
        sequence.updated_at = now
        return sequence
