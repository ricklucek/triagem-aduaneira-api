import random
from datetime import datetime
from decimal import Decimal


class NfeAccessKeyService:
    """
    Service responsável por montar a chave de acesso da NF-e.

    Estrutura da chave:
    cUF      02
    AAMM     04
    CNPJ     14
    mod      02
    serie    03
    nNF      09
    tpEmis   01
    cNF      08
    cDV      01
    Total    44
    """

    UF_CODE_MAP = {
        "RO": "11",
        "AC": "12",
        "AM": "13",
        "RR": "14",
        "PA": "15",
        "AP": "16",
        "TO": "17",
        "MA": "21",
        "PI": "22",
        "CE": "23",
        "RN": "24",
        "PB": "25",
        "PE": "26",
        "AL": "27",
        "SE": "28",
        "BA": "29",
        "MG": "31",
        "ES": "32",
        "RJ": "33",
        "SP": "35",
        "PR": "41",
        "SC": "42",
        "RS": "43",
        "MS": "50",
        "MT": "51",
        "GO": "52",
        "DF": "53",
    }

    def generate_for_draft(
        self,
        *,
        draft,
        issue_datetime: datetime | None = None,
        tp_emis: str = "1",
        c_nf: str | None = None,
    ) -> dict:
        """
        Gera a chave de acesso para um NfeDraft.

        Requisitos:
        - draft.number precisa estar preenchido
        - draft.series precisa estar preenchido
        - draft.model precisa estar preenchido
        - draft.fiscal_payload["issuer"]["cnpj"] precisa existir
        - draft.fiscal_payload["issuer"]["address"]["state"] precisa existir
        """

        if not draft.number:
            raise ValueError("Número da NF-e não informado no rascunho.")

        if not draft.series:
            raise ValueError("Série da NF-e não informada no rascunho.")

        if not draft.model:
            raise ValueError("Modelo da NF-e não informado no rascunho.")

        fiscal_payload = draft.fiscal_payload or {}
        issuer = fiscal_payload.get("issuer") or {}
        address = issuer.get("address") or {}

        cnpj = self._only_digits(issuer.get("cnpj"))
        if len(cnpj) != 14:
            raise ValueError("CNPJ do emitente deve conter 14 dígitos.")

        uf = str(address.get("state") or "").upper()
        c_uf = self.get_uf_code(uf)

        dt = issue_datetime or datetime.now()
        aamm = dt.strftime("%y%m")

        model = self._left_pad_numeric(draft.model, 2)
        series = self._left_pad_numeric(draft.series, 3)
        number = self._left_pad_numeric(str(draft.number), 9)

        tp_emis = self._only_digits(tp_emis)
        if len(tp_emis) != 1:
            raise ValueError("Tipo de emissão da NF-e deve conter 1 dígito.")

        c_nf = c_nf or self.generate_cnf()
        c_nf = self._left_pad_numeric(c_nf, 8)

        base_key = (
            c_uf
            + aamm
            + cnpj
            + model
            + series
            + number
            + tp_emis
            + c_nf
        )

        if len(base_key) != 43:
            raise ValueError(
                f"Base da chave de acesso inválida. Esperado 43 dígitos, recebido {len(base_key)}."
            )

        c_dv = self.calculate_check_digit(base_key)
        access_key = base_key + c_dv

        if len(access_key) != 44:
            raise ValueError(
                f"Chave de acesso inválida. Esperado 44 dígitos, recebido {len(access_key)}."
            )

        return {
            "access_key": access_key,
            "cUF": c_uf,
            "AAMM": aamm,
            "CNPJ": cnpj,
            "model": model,
            "series": series,
            "number": number,
            "tpEmis": tp_emis,
            "cNF": c_nf,
            "cDV": c_dv,
            "issue_datetime": dt,
        }

    def get_uf_code(self, uf: str) -> str:
        code = self.UF_CODE_MAP.get(uf)

        if not code:
            raise ValueError(f"UF inválida ou não mapeada para geração da chave: {uf}")

        return code

    def generate_cnf(self) -> str:
        return str(random.randint(0, 99999999)).zfill(8)

    def calculate_check_digit(self, base_key: str) -> str:
        """
        Calcula o dígito verificador da chave de acesso usando módulo 11.

        Pesos aplicados da direita para esquerda, de 2 até 9, reiniciando em 2.
        """

        if not base_key.isdigit():
            raise ValueError("Base da chave de acesso deve conter apenas números.")

        if len(base_key) != 43:
            raise ValueError("Base da chave de acesso deve conter 43 dígitos.")

        weight = 2
        total = 0

        for digit in reversed(base_key):
            total += int(digit) * weight
            weight += 1

            if weight > 9:
                weight = 2

        remainder = total % 11
        dv = 11 - remainder

        if dv >= 10:
            dv = 0

        return str(dv)

    def _only_digits(self, value) -> str:
        if value is None:
            return ""
        return "".join(filter(str.isdigit, str(value)))

    def _left_pad_numeric(self, value, size: int) -> str:
        digits = self._only_digits(value)

        if not digits:
            raise ValueError(f"Valor numérico obrigatório para campo de tamanho {size}.")

        if len(digits) > size:
            raise ValueError(
                f"Valor {digits} excede o tamanho máximo de {size} dígitos."
            )

        return digits.zfill(size)