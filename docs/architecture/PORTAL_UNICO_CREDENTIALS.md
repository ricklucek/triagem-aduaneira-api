# Credenciais do Portal Único

## Finalidade

A consulta de DUIMP usa o par de chaves gerado no Portal Único para a pessoa
jurídica intermediadora. O certificado A1 utilizado para gerar esse par não é
carregado pela API.

Os secrets esperados são:

- `PORTAL_UNICO_CLIENT_ID`
- `PORTAL_UNICO_CLIENT_SECRET`

O registro corporativo em `external_provider_connections` deve usar:

```json
{
  "provider": "portal_unico",
  "environment": "production",
  "auth_type": "api_key",
  "credentials_ref": "gcp:PORTAL_UNICO",
  "config_json": {
    "role_type": "IMPEXP"
  }
}
```

`importer_id` deve ser nulo para que a conexão seja compartilhada pelos
processos da organização.

## Cloud Run

Variáveis:

```text
GOOGLE_CLOUD_PROJECT=<id-do-projeto>
PORTAL_UNICO_SECRET_VERSION=1
```

A service account do Cloud Run recebe
`roles/secretmanager.secretAccessor` apenas nos dois secrets. Os valores não
devem ser injetados como variáveis de ambiente nem registrados em logs.

## Docker local

Para testar sem acessar o GCP, use uma conexão com
`credentials_ref=env:PORTAL_UNICO` e forneça ao container:

```text
PORTAL_UNICO_CLIENT_ID=<valor-local>
PORTAL_UNICO_CLIENT_SECRET=<valor-local>
```

Para testar o mesmo provider usado no Cloud Run, mantenha
`credentials_ref=gcp:PORTAL_UNICO`, monte credenciais ADC no container e
configure `GOOGLE_APPLICATION_CREDENTIALS` e `GOOGLE_CLOUD_PROJECT`.

Nenhum arquivo de credenciais, chave de acesso ou `.env` deve ser versionado.

## Rotação

Cada rotação cria uma nova versão nos dois secrets. Depois de validar as duas
versões, altere `PORTAL_UNICO_SECRET_VERSION` para o mesmo número e implante
uma nova revisão do Cloud Run. Não use versões diferentes para Client ID e
Client Secret.
