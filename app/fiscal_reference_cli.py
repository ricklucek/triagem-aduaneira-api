from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path
from urllib.request import Request, urlopen

import click
from flask.cli import AppGroup

from app.extensions import db
from app.models.fiscal_reference import FiscalCountry, FiscalMunicipality


IBGE_MUNICIPALITIES_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
)

fiscal_reference_cli = AppGroup(
    "fiscal-reference",
    help="Sincroniza os catálogos fiscais usados pela NF-e.",
)


def _municipality_state(item: dict) -> str:
    region = item.get("regiao-imediata") or {}
    intermediate = region.get("regiao-intermediaria") or {}
    state = intermediate.get("UF") or {}
    if state.get("sigla"):
        return str(state["sigla"]).upper()

    microregion = item.get("microrregiao") or {}
    mesoregion = microregion.get("mesorregiao") or {}
    return str((mesoregion.get("UF") or {}).get("sigla") or "").upper()


def _read_json(source_file: Path | None, source_url: str) -> list[dict]:
    if source_file:
        payload = json.loads(source_file.read_text(encoding="utf-8"))
    else:
        request = Request(source_url, headers={"User-Agent": "triagem-aduaneira-api/1.0"})
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
    if not isinstance(payload, list):
        raise click.ClickException("A fonte de municípios deve conter uma lista JSON.")
    return payload


@fiscal_reference_cli.command("sync-municipalities")
@click.option(
    "--source-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON local da API de Localidades do IBGE.",
)
@click.option("--source-url", default=IBGE_MUNICIPALITIES_URL, show_default=True)
@click.option("--deactivate-missing", is_flag=True, default=False)
def sync_municipalities(
    source_file: Path | None,
    source_url: str,
    deactivate_missing: bool,
):
    """Importa municípios de forma idempotente a partir da fonte oficial do IBGE."""
    payload = _read_json(source_file, source_url)
    seen: set[str] = set()

    try:
        for item in payload:
            code = str(item.get("id") or "").strip()
            name = str(item.get("nome") or "").strip()
            state = _municipality_state(item)
            if len(code) != 7 or not name or len(state) != 2:
                raise click.ClickException(
                    f"Município inválido na fonte: id={code!r}, nome={name!r}, uf={state!r}."
                )
            seen.add(code)
            row = db.session.get(FiscalMunicipality, code)
            if row is None:
                row = FiscalMunicipality(code=code)
                db.session.add(row)
            row.name = name
            row.state = state
            row.active = True

        deactivated = 0
        if deactivate_missing:
            for row in FiscalMunicipality.query.filter(
                FiscalMunicipality.active.is_(True)
            ).all():
                if row.code not in seen:
                    row.active = False
                    deactivated += 1

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    click.echo(
        f"Municípios sincronizados: {len(seen)}; desativados: {deactivated}."
    )


def _optional_date(value: str | None) -> date | None:
    normalized = (value or "").strip()
    return date.fromisoformat(normalized) if normalized else None


def _active_value(value: str | None) -> bool:
    return (value or "true").strip().casefold() not in {"0", "false", "nao", "não"}


@fiscal_reference_cli.command("import-countries")
@click.argument("source_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--deactivate-missing", is_flag=True, default=False)
def import_countries(source_file: Path, deactivate_missing: bool):
    """Importa CSV BACEN/ISO com colunas e vigências explícitas."""
    sample = source_file.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(sample.splitlines(), dialect=dialect))
    required = {"bacen_code", "name", "iso_alpha_2", "iso_alpha_3"}
    if not rows or not required.issubset(rows[0]):
        raise click.ClickException(
            "CSV deve conter bacen_code,name,iso_alpha_2,iso_alpha_3,"
            "valid_from,valid_until,active."
        )

    seen: set[str] = set()
    try:
        for item in rows:
            code = str(item.get("bacen_code") or "").strip().zfill(4)
            name = str(item.get("name") or "").strip()
            iso2 = str(item.get("iso_alpha_2") or "").strip().upper() or None
            iso3 = str(item.get("iso_alpha_3") or "").strip().upper() or None
            if len(code) != 4 or not code.isdigit() or not name:
                raise click.ClickException(
                    f"País inválido no CSV: código={code!r}, nome={name!r}."
                )
            if iso2 and len(iso2) != 2:
                raise click.ClickException(f"ISO alpha-2 inválido para {code}.")
            if iso3 and len(iso3) != 3:
                raise click.ClickException(f"ISO alpha-3 inválido para {code}.")

            valid_from = _optional_date(item.get("valid_from"))
            valid_until = _optional_date(item.get("valid_until"))
            if valid_from and valid_until and valid_until < valid_from:
                raise click.ClickException(f"Vigência invertida para o país {code}.")

            seen.add(code)
            row = db.session.get(FiscalCountry, code)
            if row is None:
                row = FiscalCountry(bacen_code=code)
                db.session.add(row)
            row.name = name
            row.iso_alpha_2 = iso2
            row.iso_alpha_3 = iso3
            row.valid_from = valid_from
            row.valid_until = valid_until
            row.active = _active_value(item.get("active"))

        deactivated = 0
        if deactivate_missing:
            for row in FiscalCountry.query.filter(FiscalCountry.active.is_(True)).all():
                if row.bacen_code not in seen:
                    row.active = False
                    deactivated += 1

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    click.echo(f"Países importados: {len(seen)}; desativados: {deactivated}.")
