# Referências fiscais — Checkpoint 4C

O catálogo é global e alimenta os campos fiscais da NF-e sem depender de texto livre.

## Tabelas

- fiscal_municipalities: código IBGE, nome, UF, status e atualização.
- fiscal_countries: código BACEN, ISO alpha-2/alpha-3, nome, vigência, status e atualização.

Este repositório contém somente os models SQLAlchemy. A criação/atualização física das tabelas deve ser gerada e executada pelo responsável no ambiente local; nenhum upgrade Alembic é executado ou publicado por este checkpoint.

## Carga dos municípios

A sincronização usa a API oficial de Localidades do IBGE e é idempotente:

    flask fiscal-reference sync-municipalities

Para validar antes sem acesso externo, salve a resposta oficial em JSON:

    flask fiscal-reference sync-municipalities --source-file municipios.json

A opção --deactivate-missing só deve ser usada após revisar a fonte completa.

## Carga dos países

Como a tabela oficial usada pela NF-e precisa preservar vigência, importe um CSV revisado com as colunas:

    bacen_code,name,iso_alpha_2,iso_alpha_3,valid_from,valid_until,active

Datas usam YYYY-MM-DD; limites vazios são abertos. Exemplo:

    1058,Brasil,BR,BRA,1900-01-01,,true
    1600,China,CN,CHN,1900-01-01,,true

Execute:

    flask fiscal-reference import-countries fiscal_countries.csv

A API avalia valid_from/valid_until pela active_on, que no fluxo da NF-e corresponde à data de emissão.

## Consultas

    GET /fiscal-reference/municipalities?q=curitiba&state=PR
    GET /fiscal-reference/countries?q=china&active_on=2026-08-25

Ambas exigem autenticação. A busca ignora acentos e retorna somente registros ativos; países também precisam estar vigentes na data consultada.
