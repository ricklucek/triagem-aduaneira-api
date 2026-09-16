# Assinatura XMLDSig da NF-e — Checkpoint 4H

O Checkpoint 4H conecta o certificado eCNPJ A1 cadastrado no 4G ao fluxo de
emissão. Ele assina o `infNFe`, verifica criptograficamente o resultado e
valida novamente o XML assinado no pacote XSD oficial antes de persistir uma
nova versão.

## Pré-requisitos

- rascunho fiscal válido e ainda editável;
- chave de acesso e número fiscal já reservados;
- versão XML não assinada mais recente aprovada no XSD;
- certificado A1 de produção ativo e pertencente ao CNPJ emitente;
- usuário administrador.

O frontend oferece a assinatura somente quando todos esses pré-requisitos são
atendidos. A API repete as mesmas verificações e é a autoridade final.

## Endpoint

```text
POST /nfe-drafts/{draft_id}/xml-versions/{xml_version_id}/sign
```

Payload:

```json
{
  "certificate_id": "uuid-do-certificado-ativo"
}
```

O certificado e sua senha são resolvidos no Secret Manager apenas dentro do
processo da API. Bytes, senha e referências internas nunca são enviados ao
frontend nem registrados nos eventos da emissão.

## Operação criptográfica

1. Bloqueia o rascunho durante a assinatura para serializar chamadas
   concorrentes.
2. Confirma que a versão não assinada é a versão corrente e está válida no
   XSD.
3. Resolve as versões explícitas do PFX e da senha no Secret Manager.
4. Confere validade, chave RSA, uso para assinatura digital e CNPJ.
5. Calcula o digest SHA-1 canônico do `infNFe`.
6. Gera a assinatura RSA-SHA1 envelopada exigida pelo leiaute NF-e 4.00.
7. Verifica localmente digest, referência, certificado embutido e assinatura.
8. Valida o XML assinado no XSD oficial.
9. Persiste uma versão `signed`, sem substituir o XML não assinado.

Embora SHA-1 não seja recomendado para protocolos novos, os identificadores de
algoritmo seguem o contrato XMLDSig do leiaute atual da NF-e. Para a auditoria
interna e integridade dos registros, a aplicação também grava checksums
SHA-256 do XML antes e depois da assinatura.

## Idempotência e concorrência

A identidade da assinatura combina:

```text
rascunho + versão XML não assinada + certificado
```

Uma repetição com a mesma combinação devolve a versão já assinada. Uma
tentativa de usar outro XML ou certificado para a mesma emissão é recusada.
O bloqueio de linha impede que duas requisições concorrentes criem duas
versões assinadas.

## Auditoria

Para cada assinatura são mantidos:

- emissão e certificado utilizado;
- tentativa e número sequencial;
- checksum SHA-256 da entrada e da saída;
- sucesso ou erro sanitizado;
- usuário e data;
- transição para `signed`;
- fingerprint e validade do certificado.

A listagem de rascunhos expõe apenas esse resumo auditável. Não expõe PFX,
senha, `certificate_ref` ou `password_ref`.

## Imutabilidade

Depois da assinatura:

- o rascunho não pode ser editado, revalidado ou regenerado;
- o XML não assinado permanece no histórico;
- o XML assinado pode ser baixado individualmente;
- planos com várias NF-e passam a gerar o ZIP com as versões assinadas;
- uma nova correção exige outro rascunho e não altera a assinatura anterior.

## Fora do escopo

O 4H não abre conexão SOAP, não envia lote, não consulta recibo e não registra
protocolo da SEFAZ. Essas operações pertencem ao Checkpoint 4I.

## Banco de dados

Não há mudança de model ou migration. O checkpoint utiliza as tabelas já
existentes:

```text
nfe_xml_versions
nfe_issuances
nfe_issuance_attempts
nfe_issuance_events
fiscal_certificates
```
