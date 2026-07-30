# Teste da NF-e de importação até o XML não assinado

Este fluxo cobre a consulta da DUIMP, criação do rascunho fiscal, cálculo dos
tributos, geração da chave, geração da NF-e 4.00 e validação XSD. Assinatura
com certificado e transmissão à SEFAZ ficam propositalmente fora desta etapa.

Todos os endpoints exigem `Authorization: Bearer <accessToken>`.

## 1. Preparar o ambiente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

O teste de integração `tests/integration/test_import_nfe_api_flow.py` executa o
fluxo completo em SQLite, com dados sanitizados, e confirma que o XML não tem
uma assinatura digital.

## 2. Configurar o perfil fiscal do emitente

Use `PUT /clients/{client_id}/fiscal-profile`. A UF informada aqui define o
`cUF`, o endereço do emitente e a chave de acesso da NF-e; ela não é fixa no
sistema.

Campos essenciais: CNPJ, IE, CRT, logradouro, município/IBGE, UF e CEP.

Se o número da NF-e não for enviado ao criar o rascunho, configure também a
sequência com `PUT /clients/{client_id}/nfe-number-sequences`.

## 3. Configurar o Portal Único

Cadastre uma conexão em `POST /external-provider-connections`:

```json
{
  "importer_id": "UUID_DO_CLIENTE",
  "provider": "portal_unico",
  "environment": "production",
  "auth_type": "api_key",
  "status": "active",
  "credentials_ref": "env:CLIENTE_ACME_PORTAL",
  "config_json": {"role_type": "IMPEXP", "timeout_seconds": 30}
}
```

As chaves não são gravadas no banco. Configure-as no processo da aplicação:

```bash
export CLIENTE_ACME_PORTAL_CLIENT_ID='...'
export CLIENTE_ACME_PORTAL_CLIENT_SECRET='...'
```

O backend autentica em `/portal/api/autenticar/chave-acesso`, conserva os
headers de token/CSRF e consulta versão, dados gerais e todas as páginas de
itens (até 100 itens por página).

## 4. Criar o processo e capturar a DUIMP

Crie o processo:

```http
POST /import-processes
```

```json
{
  "importer_id": "UUID_DO_CLIENTE",
  "reference_code": "PROCESSO-INTERNO-001",
  "duimp_number": "26BR0000000000-1",
  "source": "portal_unico"
}
```

Capture e persista o snapshot:

```http
POST /import-processes/{process_id}/duimp/fetch
```

```json
{
  "provider_environment": "production",
  "source_provider": "portal_unico",
  "enrich_catalog": true
}
```

O backend aceita a forma digitada (`26BR0000000000-1`) e envia à API a forma
compacta (`26BR00000000001`). A resposta guarda tanto o JSON bruto quanto o
contrato normalizado e seu checksum. Com `enrich_catalog=true`, cada produto e
operador estrangeiro referenciado nos itens também é consultado no Catálogo de
Produtos do Portal Único. Consultas repetidas são reaproveitadas durante a
mesma captura.

Confira `normalized_payload.catalog_enrichment` antes de criar o rascunho:

```json
{
  "products_requested": 72,
  "products_enriched": 72,
  "operators_requested": 1,
  "operators_enriched": 1,
  "failures": []
}
```

Os totais `*_enriched` devem coincidir com `*_requested` e `failures` deve
estar vazio. O rascunho fiscal rejeita a descrição genérica
`Mercadoria importada`, evitando gerar chave ou XML com um item ainda não
enriquecido.

## 5. Criar o rascunho fiscal

```http
POST /import-processes/{process_id}/nfe-draft/from-duimp
```

Exemplo mínimo para importação própria:

```json
{
  "environment": "homologation",
  "provider_environment": "production",
  "series": "1",
  "number": 123,
  "import_purpose": "resale",
  "source_provider": "portal_unico",
  "duimp_snapshot_id": "UUID_RETORNADO_NA_CAPTURA",
  "tax_configuration": {
    "icms_rate": "12",
    "icms_origin": "1",
    "icms_cst": "90",
    "ipi_cst": "49",
    "pis_cst": "98",
    "cofins_cst": "98",
    "tax_classification_code": "000001",
    "ibs_cbs_cst": "000",
    "ibs_uf_rate": "0.1",
    "ibs_mun_rate": "0",
    "cbs_rate": "0.9"
  },
  "additional_costs": {
    "afrmm": "100.00",
    "thc": "50.00",
    "other": "0.00"
  },
  "foreign_supplier": {
    "country_code": "1600",
    "country_name": "CHINA, REPUBLICA POPULAR"
  }
}
```

`foreign_supplier` continua disponível como sobrescrita quando o cadastro do
operador estrangeiro não tiver código BACEN ou endereço suficientes para a
NF-e. Nome e endereço são preenchidos automaticamente pelo Catálogo quando
estiverem disponíveis.

Quando `afrmm` e `siscomex_fee` não forem enviados em `additional_costs`, o
backend utiliza respectivamente `normalized_payload.afrmm_value` e o tributo
`taxa_utilizacao` da DUIMP. Valores enviados explicitamente, inclusive
`0.00`, sempre prevalecem. THC e outras despesas continuam sendo informados
manualmente e assumem zero quando omitidos. Alguns retornos do Portal Único
não informam AFRMM e são normalizados com valor zero; nesses casos o valor deve
ser enviado explicitamente com base no comprovante ou espelho da operação.

O `xProd` é composto pela denominação e pelo detalhamento complementar do
Catálogo, com espaços normalizados e corte na última palavra dentro do limite
de 120 caracteres da NF-e.

O valor do produto na NF-e é o valor aduaneiro da DUIMP, que já contém frete e
seguro. Por isso, `vFrete` e `vSeg` não são somados novamente. Siscomex, THC e
outras despesas são rateadas proporcionalmente ao valor aduaneiro; o AFRMM é
rateado pelo peso líquido. Quando houver AFRMM e mais de um item, todos os itens
precisam ter peso líquido positivo.

Os rateios fecham exatamente no total informado usando distribuição do resíduo
pelas maiores frações de centavo. O ICMS é calculado "por dentro". Os valores
de II, IPI, PIS e COFINS dos itens vêm da DUIMP e não são recalculados.

O payload fiscal inclui `reconciliation`. O status `balanced` confirma que os
totais oficiais disponíveis na DUIMP e todos os custos informados fecharam; o
status `requires_review` bloqueia a geração da chave e do XML até a divergência
ser corrigida.

## 6. Gerar chave e XML

```http
POST /nfe-drafts/{draft_id}/generate-access-key
Content-Type: application/json

{}
```

```http
POST /nfe-drafts/{draft_id}/generate-xml
Content-Type: application/json

{}
```

O segundo endpoint persiste uma versão `unsigned`. Verifique no XML:

- `infNFe/@Id` com a chave de 44 dígitos;
- `tpNF=0` e `idDest=3`;
- emitente brasileiro e destinatário estrangeiro (`UF=EX`);
- um grupo `DI` em cada item;
- totais de ICMS, II, IPI, PIS, COFINS e, quando configurado, IBS/CBS;
- ausência do grupo XMLDSig `Signature`.

Copie o campo `id` retornado pelo endpoint de geração. Não salve a resposta
JSON inteira como `.xml`: `xml_content` é uma string escapada dentro do JSON.
Para baixar o XML bruto, use:

```http
GET /nfe-drafts/{draft_id}/xml-versions/{xml_version_id}/download
```

A resposta tem `Content-Type: application/xml` e
`Content-Disposition: attachment`, podendo ser salva diretamente pelo cliente
HTTP ou pelo frontend.

## 7. Validar o XML no XSD oficial

```http
POST /nfe-drafts/{draft_id}/xml-versions/{xml_version_id}/validate-xsd
Content-Type: application/json

{}
```

Resposta esperada:

```json
{
  "valid": true,
  "xsd_valid": true,
  "errors": [],
  "xsd_errors": [],
  "schema": {
    "package": "PL_010e_v1.02",
    "file": "nfe_v4.00.xsd"
  }
}
```

A validação usa o pacote oficial `PL_010e_v1.02`, publicado em 10/07/2026,
compatível com os grupos IBS/CBS da NT 2025.002 v1.40. O resultado é persistido
em `nfe_xml_versions.xsd_valid` e `nfe_xml_versions.xsd_errors`.

Como o XSD de `NFe` exige `Signature`, a validação da versão `unsigned` cria
uma assinatura estrutural apenas em uma cópia em memória. O XML armazenado não
é alterado e continua sem assinatura digital. A assinatura temporária não
realiza validação criptográfica. A assinatura efetiva é realizada somente pelo
endpoint descrito a seguir, com o certificado A1 ativo do emitente.

Quando válido, o processo passa para `xml_validated`. Quando inválido, passa
para `xml_validation_failed` e a resposta informa linha, coluna, tipo e mensagem
de cada erro.

O schema já acompanha a aplicação. `NFE_XSD_PATH` só precisa ser configurada
para testar outro pacote de schemas de forma controlada.

## 8. Cadastrar e validar o certificado A1

O arquivo PFX/P12 e sua senha devem ficar em secrets distintos. No Secret
Manager, o secret do certificado contém os bytes originais do arquivo, sem
conversão para Base64. As referências salvas no banco aceitam:

- `gcp:NOME_DO_SECRET`, que usa a versão `latest`;
- `gcp:NOME_DO_SECRET@VERSAO`, que fixa uma versão numérica.

O cadastro não transfere bytes ou senha pela API:

```http
POST /clients/{client_id}/fiscal-certificates
Content-Type: application/json

{
  "environment": "homologation",
  "provider": "gcp_secret_manager",
  "certificate_ref": "gcp:nfe-hom-client-pfx@1",
  "password_ref": "gcp:nfe-hom-client-password@1"
}
```

Copie o `id` retornado e valide o material:

```http
POST /clients/{client_id}/fiscal-certificates/{certificate_id}/validate
Content-Type: application/json

{}
```

A validação abre o PKCS#12 somente em memória, exige chave privada RSA, confere
o CNPJ com o perfil fiscal, o período de validade e o uso para assinatura
digital. Quando aprovada, persiste apenas fingerprint SHA-256, serial, titular
e datas. As referências dos secrets nunca são devolvidas pela API.

Depois da conferência, ative explicitamente:

```http
POST /clients/{client_id}/fiscal-certificates/{certificate_id}/activate
Content-Type: application/json

{}
```

Somente um certificado pode permanecer ativo para cada cliente e ambiente. A
ativação desabilita o anterior. Cadastro, validação, ativação e assinatura
exigem usuário `admin`.

## 9. Assinar o XML validado

Use o `id` da versão `unsigned` mais recente e já aprovada no XSD:

```http
POST /nfe-drafts/{draft_id}/xml-versions/{unsigned_xml_version_id}/sign
Content-Type: application/json

{
  "certificate_id": "UUID_DO_CERTIFICADO_ATIVO"
}
```

Se `certificate_id` for omitido, o backend seleciona o único A1 ativo do
cliente e ambiente. A operação:

1. resolve PFX e senha sob demanda;
2. reconfirma CNPJ, validade e chave privada;
3. calcula o digest SHA-1 canonizado de `infNFe`;
4. assina `SignedInfo` com RSA-SHA1, conforme o XMLDSig exigido pelo leiaute;
5. verifica digest e assinatura com a chave pública;
6. valida o XML assinado no XSD oficial;
7. persiste uma versão `signed` sem sobrescrever a `unsigned`;
8. registra emissão, tentativa, checksums e transição de estado.

Resposta esperada:

```json
{
  "replayed": false,
  "issuance": {
    "status": "signed",
    "access_key": "CHAVE_DE_44_DIGITOS"
  },
  "xml_version": {
    "xml_type": "SIGNED",
    "xsd_valid": true,
    "xsd_errors": []
  }
}
```

Repetir a mesma requisição devolve HTTP `200`, `replayed=true` e a mesma versão
assinada. A primeira execução devolve HTTP `201`. O processo passa para
`xml_signed`.

Baixe o arquivo assinado pelo endpoint já existente:

```http
GET /nfe-drafts/{draft_id}/xml-versions/{signed_xml_version_id}/download
```

## Modalidades

O normalizador reconhece `direct`, `on_behalf` e `by_order`. Para conta e ordem
ou encomenda, informe também em `duimp_overrides`:

```json
{
  "intermediation_type": "2",
  "third_party_tax_id": "CNPJ_OU_CPF",
  "third_party_state": "SP"
}
```

Use `intermediation_type=2` para conta e ordem e `3` para encomenda. Esta etapa
gera a NF-e de entrada vinculada à DUIMP. Eventuais notas subsequentes entre a
importadora e adquirente/encomendante devem ser tratadas como outro documento
fiscal, com regras próprias.

## Limites desta etapa

- A assinatura A1 está implementada, mas ainda não há transmissão, recibo,
  protocolo de autorização ou eventos fiscais enviados à SEFAZ.
- A aprovação no XSD comprova a conformidade estrutural, mas não executa as
  regras de negócio aplicadas pela autorização da SEFAZ.
- O cálculo usa parâmetros explícitos porque ICMS e benefícios dependem da UF,
  NCM, finalidade, regime e enquadramento do cliente.
- Antes de produção, compare uma amostra representativa com o cálculo do
  despachante/ERP e execute a autorização no ambiente de homologação da SEFAZ.
