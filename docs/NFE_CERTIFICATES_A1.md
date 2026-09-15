# Certificados eCNPJ A1 — Checkpoint 4G

Este checkpoint permite que um administrador envie o arquivo PKCS#12 do
cliente pela aplicação. O arquivo e a senha são validados em memória antes de
qualquer persistência.

## Fluxo

1. O administrador seleciona o cliente emitente.
2. A interface envia um `.pfx` ou `.p12`, a senha e o ambiente fiscal por
   `multipart/form-data`.
3. A API valida a senha, a chave privada RSA, o uso para assinatura digital,
   a validade e o CNPJ do certificado.
4. O PFX e a senha são gravados em secrets separados no Google Secret Manager.
5. A API relê as duas versões e confirma o conteúdo armazenado antes de
   concluir o cadastro.
6. O banco recebe apenas referências com versões explícitas e os metadados do
   certificado.
7. Ao ativar uma nova versão, o certificado ativo anterior do mesmo cliente e
   ambiente passa para `disabled`, permanecendo no histórico.

O limite do arquivo é 64 KiB, igual ao limite do payload de uma versão no
Secret Manager. O conteúdo do arquivo, a senha e as referências internas dos
secrets nunca são devolvidos pela API.

## Endpoints

```text
GET  /clients/{client_id}/fiscal-certificates
POST /clients/{client_id}/fiscal-certificates/upload
POST /clients/{client_id}/fiscal-certificates/{certificate_id}/validate
POST /clients/{client_id}/fiscal-certificates/{certificate_id}/activate
POST /clients/{client_id}/fiscal-certificates/{certificate_id}/deactivate
```

A consulta exige autenticação. Upload, validação, ativação e desativação exigem
administrador.

O upload recebe:

```text
certificate  arquivo .pfx ou .p12
password     senha do PKCS#12
environment  production ou homologation
activate     true ou false
```

A interface do 4G fixa `production`, seguindo o contrato atual das novas
emissões.

## Secret Manager

Cada upload cria dois secrets exclusivos:

```text
nfe-a1-{organization_id}-{client_id}-{certificate_id}-pfx
nfe-a1-{organization_id}-{client_id}-{certificate_id}-password
```

As referências persistidas usam o número exato da versão, nunca o alias
`latest`. Isso impede que arquivo e senha sejam combinados com versões
diferentes durante uma assinatura futura.

O projeto já fornece `GOOGLE_CLOUD_PROJECT` ao Cloud Run. A conta de serviço de
execução precisa destas permissões:

```text
secretmanager.secrets.create
secretmanager.secrets.delete
secretmanager.versions.add
secretmanager.versions.access
```

`secretmanager.secrets.delete` é utilizado somente na compensação de um upload
parcial que falhe antes da conclusão. Recomenda-se criar uma função IAM
personalizada com apenas essas permissões e atribuí-la à conta de execução do
serviço `ta-api`.

Exemplo de preparação, substituindo os valores entre `<>`:

```bash
gcloud services enable secretmanager.googleapis.com \
  --project=<PROJECT_ID>

gcloud iam roles create nfeA1CertificateManager \
  --project=<PROJECT_ID> \
  --title="NF-e A1 Certificate Manager" \
  --stage=GA \
  --permissions=secretmanager.secrets.create,secretmanager.secrets.delete,secretmanager.versions.add,secretmanager.versions.access

gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:<CLOUD_RUN_SERVICE_ACCOUNT>" \
  --role="projects/<PROJECT_ID>/roles/nfeA1CertificateManager"
```

Para descobrir a conta atualmente usada:

```bash
gcloud run services describe ta-api \
  --region southamerica-east1 \
  --format='value(spec.template.spec.serviceAccountName)'
```

Caso o comando não retorne uma conta explícita, o Cloud Run está usando a
conta padrão do projeto. Antes da publicação em produção, prefira configurar
uma conta dedicada para a API.

Documentação oficial utilizada:

- https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets
- https://cloud.google.com/secret-manager/docs/add-secret-version
- https://cloud.google.com/secret-manager/docs/access-secret-version
- https://cloud.google.com/secret-manager/docs/access-control

## Banco de dados

Não há alteração de model neste checkpoint. A tabela `fiscal_certificates` já
armazena as referências, CNPJ, fingerprint SHA-256, serial, assunto, validade,
status, usuário criador e datas de validação/criação.

Nenhuma migration precisa ser criada ou executada para o 4G, desde que as
tabelas de emissão publicadas nos checkpoints anteriores já estejam presentes.

## Limites do checkpoint

O 4G não disponibiliza download do certificado e não assina ou transmite XML.
A seleção do certificado e a assinatura XMLDSig pertencem ao Checkpoint 4H; a
comunicação com a SEFAZ pertence ao 4I.
