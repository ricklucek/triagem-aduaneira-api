from types import SimpleNamespace

from app.services.fiscal_certificate import (
    GcpSecretManagerCertificateVault,
)
from tests.helpers import certificate_material


class FakeSecretManagerClient:
    def __init__(self):
        self.secrets = {}

    def create_secret(self, *, request):
        name = f"{request['parent']}/secrets/{request['secret_id']}"
        self.secrets[name] = []
        return SimpleNamespace(name=name)

    def add_secret_version(self, *, request):
        versions = self.secrets[request["parent"]]
        versions.append(bytes(request["payload"]["data"]))
        return SimpleNamespace(
            name=f"{request['parent']}/versions/{len(versions)}"
        )

    def access_secret_version(self, *, request):
        secret_name, version = request["name"].rsplit("/versions/", 1)
        payload = self.secrets[secret_name][int(version) - 1]
        return SimpleNamespace(payload=SimpleNamespace(data=payload))

    def delete_secret(self, *, request):
        self.secrets.pop(request["name"], None)


def test_gcp_vault_stores_and_resolves_explicit_secret_versions():
    client = FakeSecretManagerClient()
    vault = GcpSecretManagerCertificateVault(
        client=client,
        project_id="project-test",
    )
    material = certificate_material("00000000000191")

    references = vault.store(
        organization_id="11111111-1111-1111-1111-111111111111",
        client_id="22222222-2222-2222-2222-222222222222",
        certificate_id="33333333-3333-3333-3333-333333333333",
        material=material,
    )
    resolved = vault.resolve(
        provider="gcp_secret_manager",
        certificate_ref=references.certificate_ref,
        password_ref=references.password_ref,
    )

    assert references.certificate_ref.endswith("-pfx@1")
    assert references.password_ref.endswith("-password@1")
    assert resolved == material
