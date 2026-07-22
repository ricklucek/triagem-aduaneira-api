from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


class ImportTaxCalculationError(ValueError):
    pass


class ImportTaxCalculator:
    MONEY = Decimal("0.01")
    RATE = Decimal("0.0001")

    def calculate(
        self,
        items: list[dict[str, Any]],
        *,
        configuration: dict[str, Any],
        additional_costs: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        if not items:
            raise ImportTaxCalculationError("Não existem itens para calcular.")

        icms_rate = self._decimal(configuration.get("icms_rate"))
        if not Decimal("0") < icms_rate < Decimal("100"):
            raise ImportTaxCalculationError(
                "A alíquota de ICMS deve ser maior que zero e menor que 100."
            )

        costs = additional_costs or {}
        afrmm_total = self._money(costs.get("afrmm"))
        other_total = self._money(
            self._decimal(costs.get("siscomex_fee"))
            + self._decimal(costs.get("thc"))
            + self._decimal(costs.get("other"))
        )
        weights = [self._money(item.get("product_value")) for item in items]
        afrmm_allocations = self.allocate(afrmm_total, weights)
        other_allocations = self.allocate(other_total, weights)

        calculated_items: list[dict[str, Any]] = []
        for index, source in enumerate(items):
            item = deepcopy(source)
            existing_other = self._money(item.get("other_value"))
            item_afrmm = afrmm_allocations[index]
            item_other = existing_other + item_afrmm + other_allocations[index]
            item["other_value"] = self._format_money(item_other)

            taxes = deepcopy(item.get("tax_payload") or item.get("taxes") or {})
            ii = self._tax(taxes, "ii")
            ipi = self._tax(taxes, "ipi")
            pis = self._tax(taxes, "pis")
            cofins = self._tax(taxes, "cofins")

            product_value = self._money(item.get("product_value"))
            discount = self._money(item.get("discount_value"))
            icms_base_numerator = (
                product_value
                + ii["value"]
                + ipi["value"]
                + pis["value"]
                + cofins["value"]
                + item_other
                - discount
            )
            icms_base = self._money(
                icms_base_numerator / (Decimal("1") - icms_rate / Decimal("100"))
            )
            icms_value = self._money(icms_base * icms_rate / Decimal("100"))

            taxes["icms"] = {
                "origin": str(configuration.get("icms_origin") or "1"),
                "cst": str(configuration.get("icms_cst") or "90").zfill(2),
                "base_method": str(configuration.get("icms_base_method") or "3"),
                "base": self._format_money(icms_base),
                "rate": self._format_rate(icms_rate),
                "value": self._format_money(icms_value),
                "st_base_method": str(configuration.get("icms_st_base_method") or "6"),
                "st_base": "0.00",
                "st_rate": "0.0000",
                "st_value": "0.00",
            }
            taxes["ipi"] = {
                **taxes.get("ipi", {}),
                "cst": str(configuration.get("ipi_cst") or "49").zfill(2),
                "enquiry_code": str(configuration.get("ipi_enquiry_code") or "999"),
                "base": self._format_money(ipi["base"]),
                "rate": self._format_rate(ipi["rate"]),
                "value": self._format_money(ipi["value"]),
            }
            taxes["ii"] = {
                **taxes.get("ii", {}),
                "base": self._format_money(ii["base"] or product_value),
                "customs_expenses": self._format_money(ii["customs_expenses"]),
                "value": self._format_money(ii["value"]),
                "iof": self._format_money(ii["iof"]),
            }
            taxes["pis"] = {
                **taxes.get("pis", {}),
                "cst": str(configuration.get("pis_cst") or "98").zfill(2),
                "base": self._format_money(pis["base"] or product_value),
                "rate": self._format_rate(pis["rate"]),
                "value": self._format_money(pis["value"]),
            }
            taxes["cofins"] = {
                **taxes.get("cofins", {}),
                "cst": str(configuration.get("cofins_cst") or "98").zfill(2),
                "base": self._format_money(cofins["base"] or product_value),
                "rate": self._format_rate(cofins["rate"]),
                "value": self._format_money(cofins["value"]),
            }

            classification = (
                item.get("tax_classification_code")
                or configuration.get("tax_classification_code")
            )
            if classification:
                ibs_uf_rate = self._decimal(configuration.get("ibs_uf_rate"))
                ibs_mun_rate = self._decimal(configuration.get("ibs_mun_rate"))
                cbs_rate = self._decimal(configuration.get("cbs_rate"))
                ibs_cbs_base = self._money(
                    product_value
                    + ii["value"]
                    + item_other
                    - icms_value
                    - pis["value"]
                    - cofins["value"]
                    - discount
                )
                ibs_uf_value = self._money(
                    ibs_cbs_base * ibs_uf_rate / Decimal("100")
                )
                ibs_mun_value = self._money(
                    ibs_cbs_base * ibs_mun_rate / Decimal("100")
                )
                cbs_value = self._money(ibs_cbs_base * cbs_rate / Decimal("100"))
                taxes["ibs_cbs"] = {
                    "cst": str(configuration.get("ibs_cbs_cst") or "000").zfill(3),
                    "classification": str(classification).zfill(6),
                    "base": self._format_money(ibs_cbs_base),
                    "ibs_uf_rate": self._format_rate(ibs_uf_rate),
                    "ibs_uf_value": self._format_money(ibs_uf_value),
                    "ibs_mun_rate": self._format_rate(ibs_mun_rate),
                    "ibs_mun_value": self._format_money(ibs_mun_value),
                    "ibs_value": self._format_money(ibs_uf_value + ibs_mun_value),
                    "cbs_rate": self._format_rate(cbs_rate),
                    "cbs_value": self._format_money(cbs_value),
                }

            import_payload = deepcopy(item.get("import_payload") or {})
            import_payload["afrmm_value"] = self._format_money(item_afrmm)
            item["import_payload"] = import_payload
            item["tax_payload"] = taxes
            calculated_items.append(item)

        return calculated_items, self.calculate_totals(calculated_items)

    def calculate_totals(self, items: list[dict[str, Any]]) -> dict[str, str]:
        fields = {
            "products_value": Decimal("0"),
            "freight_value": Decimal("0"),
            "insurance_value": Decimal("0"),
            "discount_value": Decimal("0"),
            "other_value": Decimal("0"),
            "ii_value": Decimal("0"),
            "ipi_value": Decimal("0"),
            "pis_value": Decimal("0"),
            "cofins_value": Decimal("0"),
            "icms_base": Decimal("0"),
            "icms_value": Decimal("0"),
            "ibs_cbs_base": Decimal("0"),
            "ibs_uf_value": Decimal("0"),
            "ibs_mun_value": Decimal("0"),
            "ibs_value": Decimal("0"),
            "cbs_value": Decimal("0"),
        }
        for item in items:
            fields["products_value"] += self._money(item.get("product_value"))
            fields["freight_value"] += self._money(item.get("freight_value"))
            fields["insurance_value"] += self._money(item.get("insurance_value"))
            fields["discount_value"] += self._money(item.get("discount_value"))
            fields["other_value"] += self._money(item.get("other_value"))
            taxes = item.get("tax_payload") or {}
            for tax, field in {
                "ii": "ii_value",
                "ipi": "ipi_value",
                "pis": "pis_value",
                "cofins": "cofins_value",
                "icms": "icms_value",
            }.items():
                fields[field] += self._money((taxes.get(tax) or {}).get("value"))
            fields["icms_base"] += self._money(
                (taxes.get("icms") or {}).get("base")
            )
            ibs_cbs = taxes.get("ibs_cbs") or {}
            for key in [
                "ibs_cbs_base",
                "ibs_uf_value",
                "ibs_mun_value",
                "ibs_value",
                "cbs_value",
            ]:
                source = "base" if key == "ibs_cbs_base" else key.removeprefix("ibs_")
                if key == "ibs_uf_value":
                    source = "ibs_uf_value"
                elif key == "ibs_mun_value":
                    source = "ibs_mun_value"
                elif key == "ibs_value":
                    source = "ibs_value"
                elif key == "cbs_value":
                    source = "cbs_value"
                fields[key] += self._money(ibs_cbs.get(source))

        invoice_value = (
            fields["products_value"]
            + fields["freight_value"]
            + fields["insurance_value"]
            + fields["other_value"]
            + fields["ii_value"]
            + fields["ipi_value"]
            + fields["pis_value"]
            + fields["cofins_value"]
            + fields["icms_value"]
            - fields["discount_value"]
        )
        rtc_invoice_value = (
            fields["products_value"]
            + fields["freight_value"]
            + fields["insurance_value"]
            + fields["other_value"]
            + fields["ii_value"]
            + fields["ipi_value"]
            - fields["discount_value"]
        )
        fields["invoice_value"] = invoice_value
        fields["rtc_invoice_value"] = rtc_invoice_value
        return {key: self._format_money(value) for key, value in fields.items()}

    def allocate(self, total: Decimal, weights: list[Decimal]) -> list[Decimal]:
        total = self._money(total)
        if not weights:
            return []
        weight_total = sum(weights, Decimal("0"))
        if total == 0:
            return [Decimal("0.00") for _ in weights]
        if weight_total <= 0:
            raise ImportTaxCalculationError(
                "Não é possível ratear despesas sem valores de produto positivos."
            )

        allocations: list[Decimal] = []
        allocated = Decimal("0")
        for index, weight in enumerate(weights):
            if index == len(weights) - 1:
                value = total - allocated
            else:
                value = self._money(total * weight / weight_total)
                allocated += value
            allocations.append(self._money(value))
        return allocations

    def _tax(self, taxes: dict[str, Any], name: str) -> dict[str, Decimal]:
        data = taxes.get(name) or {}
        return {
            "value": self._money(data.get("value")),
            "base": self._money(data.get("base")),
            "rate": self._decimal(data.get("rate")),
            "customs_expenses": self._money(data.get("customs_expenses")),
            "iof": self._money(data.get("iof")),
        }

    def _money(self, value: Any) -> Decimal:
        return self._decimal(value).quantize(self.MONEY, rounding=ROUND_HALF_UP)

    def _format_money(self, value: Any) -> str:
        return format(self._money(value), ".2f")

    def _format_rate(self, value: Any) -> str:
        return format(
            self._decimal(value).quantize(self.RATE, rounding=ROUND_HALF_UP), ".4f"
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value if value not in (None, "") else "0"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ImportTaxCalculationError(f"Valor numérico inválido: {value}") from exc
