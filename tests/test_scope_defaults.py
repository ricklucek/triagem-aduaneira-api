import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "scope_defaults.py"
SPEC = importlib.util.spec_from_file_location("scope_defaults", MODULE_PATH)
scope_defaults = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(scope_defaults)

build_default_scope_draft = scope_defaults.build_default_scope_draft
merge_scope_draft = scope_defaults.merge_scope_draft


class ScopeFreightDefaultsTestCase(unittest.TestCase):
    def test_legacy_freight_payload_defaults_to_casco(self):
        legacy_payload = {
            "servicos": {
                "importacao": {
                    "freteInternacional": {
                        "habilitado": True,
                        "modalidade": "SIM",
                        "ptaxNegociado": "1.5",
                    }
                }
            }
        }

        normalized = merge_scope_draft(build_default_scope_draft(), legacy_payload)
        freight = normalized["servicos"]["importacao"]["freteInternacional"]

        self.assertEqual(freight["responsavelFrete"], "CASCO")
        self.assertEqual(freight["prestadoresTerceiros"], [])
        self.assertEqual(freight["modalidade"], "SIM")
        self.assertEqual(freight["ptaxNegociado"], "1.5")

    def test_third_party_providers_are_preserved_for_both_operations(self):
        provider = {
            "empresa": "Freight Partner",
            "nomeSistema": "Partner Portal",
            "url": "https://partner.example.com",
            "login": "casco.operator",
            "senha": "secret-value",
            "contato": "Equipe operacional",
            "observacoes": "Conta usada para embarques urgentes.",
        }
        payload = {
            "servicos": {
                operation: {
                    "freteInternacional": {
                        "habilitado": True,
                        "modalidade": "CASO_A_CASO",
                        "responsavelFrete": "TERCEIRO",
                        "prestadoresTerceiros": [provider],
                    }
                }
                for operation in ("importacao", "exportacao")
            }
        }

        normalized = merge_scope_draft(build_default_scope_draft(), payload)

        for operation in ("importacao", "exportacao"):
            freight = normalized["servicos"][operation]["freteInternacional"]
            self.assertEqual(freight["responsavelFrete"], "TERCEIRO")
            self.assertEqual(freight["prestadoresTerceiros"], [provider])


if __name__ == "__main__":
    unittest.main()
