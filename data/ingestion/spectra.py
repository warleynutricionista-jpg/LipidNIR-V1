"""Interpretação de espectros: layouts largo, longo e arquivo único.

Esta é a única implementação de parsing, normalização de eixo e interpretação de sinal.
A base experimental e a predição chamam ``parse_spectra`` (INV-2).
"""

from __future__ import annotations

import enum
from collections import defaultdict
from pathlib import PurePath

import numpy as np

from lipidence_modular.core.errors import IdentityConflictError, IdentityError
from lipidence_modular.data.identity.normalization import normalize_sample_id
from lipidence_modular.data.identity.resolution import FieldOrigin, resolve_sample_id
from lipidence_modular.data.importers.table import RawTable, is_blank, to_float
from lipidence_modular.data.ingestion.plan import ImportPlan, SignalScale
from lipidence_modular.data.mapping import roles
from lipidence_modular.data.schemas.issues import IssueLog
from lipidence_modular.data.schemas.spectral import AxisUnit, ParsedSpectrum, SignalType
from lipidence_modular.data.validators.spectral_quality import validate_spectrum


class SpectralLayout(enum.StrEnum):
    WIDE = "wide"
    LONG = "long"
    SINGLE = "single"


class PlanError(ValueError):
    """O plano não permite interpretar o arquivo; nada é importado até ser corrigido."""


FILE_ITEM = "arquivo"


def detect_layout(mapping: dict[str, str]) -> SpectralLayout:
    assigned = list(mapping.values())
    has_spectral = roles.SPECTRAL in assigned
    has_pair = roles.WAVELENGTH in assigned and roles.SIGNAL in assigned
    if has_spectral and has_pair:
        raise PlanError("mapeamento mistura layout largo (colunas espectrais) e longo")
    if has_spectral:
        if roles.SAMPLE_ID not in assigned:
            raise PlanError("layout largo exige uma coluna mapeada como sample_id")
        return SpectralLayout.WIDE
    if has_pair:
        return SpectralLayout.LONG if roles.SAMPLE_ID in assigned else SpectralLayout.SINGLE
    raise PlanError(
        "nenhum layout espectral reconhecido: mapeie colunas espectrais (largo) ou "
        "wavelength + signal (longo ou arquivo único)"
    )


def require_declarations(plan: ImportPlan) -> None:
    """Tipo de sinal e unidade do eixo são perguntados, nunca adivinhados (INV-7)."""
    missing = [name for name, value in (("signal_type", plan.signal_type),
                                        ("wavelength_unit", plan.wavelength_unit))
               if value is None]
    if missing:
        raise PlanError(f"declaração obrigatória ausente: {', '.join(missing)}")
    if plan.convert_to_absorbance:
        if plan.signal_type is SignalType.ABSORBANCE:
            raise PlanError("convert_to_absorbance não se aplica a sinal já em absorbância")
        if plan.signal_scale is None:
            raise PlanError("conversão para absorbância exige signal_scale (fraction ou percent)")


def to_canonical_axis(axis: np.ndarray, unit: AxisUnit) -> tuple[np.ndarray, list[str]]:
    """Eixo na unidade canônica (nm). A conversão é explícita e registrada."""
    if unit is AxisUnit.NM:
        return axis, []
    if np.any(~np.isfinite(axis)) or np.any(axis <= 0):
        return np.full_like(axis, np.nan), ["eixo em cm-1 com valor inválido"]
    return 1.0e7 / axis, ["eixo convertido de cm-1 para nm (nm = 1e7 / cm-1)"]


def _single_role(mapping: dict[str, str], role: str) -> str | None:
    columns = [c for c, r in mapping.items() if r == role]
    if len(columns) > 1:
        raise PlanError(f"mais de uma coluna mapeada como {role}: {columns}")
    return columns[0] if columns else None


def _prefixed(mapping: dict[str, str], prefix: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for column, role in mapping.items():
        if role.startswith(prefix):
            name = role[len(prefix):]
            if name in result.values():
                raise PlanError(f"mais de uma coluna mapeada como {role}")
            result[column] = name
    return result


def row_metadata(table: RawTable, row: list[object], columns: dict[str, str]) -> dict[str, str]:
    return {
        name: str(row[table.column_index(column)]).strip()
        for column, name in columns.items()
        if not is_blank(row[table.column_index(column)])
    }


def merge_metadata(defaults: dict[str, str],
                   from_file: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Metadados finais e a origem de cada campo. O valor do arquivo prevalece sobre o
    padrão informado para o arquivo inteiro."""
    merged = {**defaults, **from_file}
    origins = {name: FieldOrigin.USER_ENTERED.value for name in defaults}
    origins.update({name: FieldOrigin.FILE.value for name in from_file})
    return merged, origins


def _convert_signal(values: np.ndarray, plan: ImportPlan) -> tuple[np.ndarray, SignalType,
                                                                  list[str], str | None]:
    if not plan.convert_to_absorbance:
        return values, plan.signal_type, [], None
    fraction = values / 100.0 if plan.signal_scale is SignalScale.PERCENT else values
    if np.any(~np.isfinite(fraction)) or np.any(fraction <= 0):
        return values, plan.signal_type, [], (
            "conversão para absorbância impossível: sinal ausente, nulo ou negativo"
        )
    letter = "R" if plan.signal_type is SignalType.REFLECTANCE else "T"
    note = (f"sinal convertido de {plan.signal_type.value} ({plan.signal_scale.value}) "
            f"para absorbância: log10(1/{letter})")
    return np.log10(1.0 / fraction), SignalType.ABSORBANCE, [note], None


def _finish(item: str, identity, origin, replicate, axis_raw, values_raw,
            plan: ImportPlan, log: IssueLog, meta, thresholds) -> ParsedSpectrum | None:
    sample_meta, origins, spectrum_meta = meta
    axis, provenance = to_canonical_axis(np.asarray(axis_raw, dtype=float), plan.wavelength_unit)
    values = np.asarray(values_raw, dtype=float)
    order = np.argsort(axis, kind="stable")
    if not np.array_equal(order, np.arange(axis.size)) and np.all(np.isfinite(axis)):
        axis, values = axis[order], values[order]
        provenance = [*provenance, "pontos reordenados para eixo crescente"]
    values, signal_type, notes, error = _convert_signal(values, plan)
    if error:
        log.reject(item, "signal_conversion", error)
        return None
    report = validate_spectrum(
        axis, values, is_absorbance=signal_type is SignalType.ABSORBANCE, thresholds=thresholds
    )
    for issue in report.errors:
        log.reject(item, issue.code, issue.message)
    for issue in report.warnings:
        log.alert(item, issue.code, issue.message)
    if not report.is_valid:
        return None
    return ParsedSpectrum(
        item=item, sample_id=identity.sample_id, sample_id_raw=identity.sample_id_raw,
        sample_id_origin=origin, technical_replicate=replicate, axis_nm=axis, values=values,
        signal_type=signal_type, sample_metadata=sample_meta, spectrum_metadata=spectrum_meta,
        provenance=[*provenance, *notes], metadata_origins=origins,
    )


def _identity_from_cell(cell: object, item: str, log: IssueLog):
    try:
        return normalize_sample_id(cell)
    except IdentityError as exc:
        log.reject(item, "sample_id_missing", f"sample_id ausente ou inválido: {exc}")
        return None


def _replicate_cell(table: RawTable, row, column: str | None, item: str, log: IssueLog):
    """(replicata, ok). Coluna não mapeada ou célula vazia: ``None``."""
    if column is None or is_blank(row[table.column_index(column)]):
        return None, True
    number = to_float(row[table.column_index(column)], table.detection.decimal)
    if number is None or number < 1 or not float(number).is_integer():
        log.reject(item, "replicate_invalid", "replicata técnica deve ser inteiro ≥ 1")
        return None, False
    return int(number), True


def _apply_duplicate_policy(spectra: list[ParsedSpectrum], plan: ImportPlan,
                            log: IssueLog) -> list[ParsedSpectrum]:
    """Mesma amostra repetida no arquivo: só vira replicata técnica quando declarado."""
    groups: dict[str, list[ParsedSpectrum]] = defaultdict(list)
    for spectrum in spectra:
        groups[spectrum.sample_id].append(spectrum)
    kept: list[ParsedSpectrum] = []
    for sample_id, group in groups.items():
        explicit = [s.technical_replicate for s in group if s.technical_replicate is not None]
        if len(group) == 1:
            kept.extend(group)
        elif len(explicit) == len(group):
            if len(set(explicit)) != len(explicit):
                for s in group:
                    log.reject(s.item, "duplicate_replicate",
                               f"{sample_id}: replicata técnica repetida no arquivo")
            else:
                kept.extend(group)
        elif explicit:
            for s in group:
                log.reject(s.item, "replicate_partial",
                           f"{sample_id}: replicata técnica informada só em parte das linhas")
        elif plan.repeated_rows_are_replicates:
            for number, s in enumerate(group, start=1):
                s.technical_replicate = number
                s.provenance.append("linhas repetidas declaradas como replicatas técnicas")
            kept.extend(group)
        else:
            for s in group:
                log.reject(s.item, "duplicate_sample_id", f"{sample_id}: sample_id duplicado")
    return kept


def _apply_user_identity(spectra: list[ParsedSpectrum],
                         plan: ImportPlan) -> list[ParsedSpectrum]:
    """Identidade informada pelo usuário para um arquivo que já traz ``sample_id``.

    Só faz sentido quando o arquivo tem uma única amostra. Se os valores diferem, levanta
    ``IdentityConflictError`` até haver confirmação explícita (seção 8.4)."""
    if not plan.user_sample_id or not spectra:
        return spectra
    file_ids = {s.sample_id for s in spectra}
    if len(file_ids) > 1:
        raise PlanError("user_sample_id só se aplica a arquivo com uma única amostra")
    resolved = resolve_sample_id(
        from_file=next(iter(file_ids)), user_value=plan.user_sample_id,
        conflict_confirmed=plan.conflict_confirmed,
    )
    for spectrum in spectra:
        if spectrum.sample_id != resolved.value:
            spectrum.provenance.append(
                f"sample_id do arquivo ({spectrum.sample_id}) substituído por confirmação "
                f"do usuário ({resolved.value})"
            )
        spectrum.sample_id = resolved.value
        spectrum.sample_id_raw = resolved.raw
        spectrum.sample_id_origin = resolved.origin
    return spectra


def parse_spectra(table: RawTable, mapping: dict[str, str], plan: ImportPlan, filename: str,
                  log: IssueLog, thresholds: dict | None = None) -> list[ParsedSpectrum]:
    """Espectros válidos do arquivo. Itens rejeitados ficam só no ``log``."""
    require_declarations(plan)
    layout = detect_layout(mapping)
    decimal = table.detection.decimal
    sample_cols = _prefixed(mapping, roles.META_PREFIX)
    spectrum_cols = _prefixed(mapping, roles.SPECTRUM_PREFIX)
    replicate_col = _single_role(mapping, roles.TECHNICAL_REPLICATE)
    spectra: list[ParsedSpectrum] = []

    def metadata(row):
        return (*merge_metadata(plan.sample_defaults, row_metadata(table, row, sample_cols)),
                {**plan.spectrum_defaults, **row_metadata(table, row, spectrum_cols)})

    if layout is SpectralLayout.WIDE:
        id_col = table.column_index(_single_role(mapping, roles.SAMPLE_ID))
        spectral = [c for c, r in mapping.items() if r == roles.SPECTRAL]
        axis_raw = [to_float(roles.split_header_unit(c)[0], decimal) for c in spectral]
        if any(v is None for v in axis_raw):
            raise PlanError("coluna espectral com cabeçalho não numérico")
        indices = [table.column_index(c) for c in spectral]
        for number, row in enumerate(table.rows, start=1):
            identity = _identity_from_cell(row[id_col], f"linha {number}", log)
            if identity is None:
                continue
            item_label = f"{identity.sample_id} (linha {number})"
            log.register(item_label)
            replicate, ok = _replicate_cell(table, row, replicate_col, item_label, log)
            if not ok:
                continue
            cells = [row[i] for i in indices]
            values = [to_float(c, decimal) for c in cells]
            bad_text = sum(1 for c, v in zip(cells, values, strict=True)
                           if v is None and not is_blank(c))
            if bad_text:
                log.reject(item_label, "non_numeric", f"{bad_text} valor(es) não numérico(s)")
                continue
            values = [np.nan if v is None else v for v in values]
            parsed = _finish(item_label, identity, FieldOrigin.FILE, replicate, axis_raw, values,
                             plan, log, metadata(row), thresholds)
            if parsed:
                spectra.append(parsed)
        return _apply_user_identity(_apply_duplicate_policy(spectra, plan, log), plan)

    wl_col = table.column_index(_single_role(mapping, roles.WAVELENGTH))
    sig_col = table.column_index(_single_role(mapping, roles.SIGNAL))

    if layout is SpectralLayout.LONG:
        id_col = table.column_index(_single_role(mapping, roles.SAMPLE_ID))
        groups: dict[tuple[str, int | None], dict] = {}
        for number, row in enumerate(table.rows, start=1):
            if is_blank(row[id_col]):
                item = f"linha {number}"
                log.reject(item, "sample_id_missing", "sample_id ausente")
                continue
            identity = _identity_from_cell(row[id_col], f"linha {number}", log)
            if identity is None:
                continue
            replicate, ok = _replicate_cell(table, row, replicate_col, identity.sample_id, log)
            if not ok:
                continue
            group = groups.setdefault((identity.sample_id, replicate), {
                "identity": identity, "axis": [], "values": [], "bad": 0, "row": row,
            })
            wl, sig = to_float(row[wl_col], decimal), to_float(row[sig_col], decimal)
            if wl is None or (sig is None and not is_blank(row[sig_col])):
                group["bad"] += 1
            group["axis"].append(np.nan if wl is None else wl)
            group["values"].append(np.nan if sig is None else sig)
        for (sample_id, replicate), group in groups.items():
            item = sample_id if replicate is None else f"{sample_id} (replicata {replicate})"
            log.register(item)
            if log.is_rejected(sample_id):
                continue
            if group["bad"]:
                log.reject(item, "non_numeric",
                           f"{group['bad']} linha(s) com comprimento de onda ou sinal inválido")
                continue
            parsed = _finish(item, group["identity"], FieldOrigin.FILE, replicate,
                             group["axis"], group["values"], plan, log,
                             metadata(group["row"]), thresholds)
            if parsed:
                spectra.append(parsed)
        return _apply_user_identity(spectra, plan)

    # Arquivo único: duas colunas, uma amostra. O nome do arquivo é só sugestão.
    suggestion = PurePath(filename).stem
    try:
        resolved = resolve_sample_id(
            auto_detected=suggestion, user_value=plan.user_sample_id,
            conflict_confirmed=plan.conflict_confirmed,
        )
    except IdentityConflictError:
        raise
    except IdentityError as exc:
        log.reject(FILE_ITEM, "sample_id_unconfirmed", str(exc))
        return []
    item = resolved.value
    log.register(item)
    cells = [(row[wl_col], row[sig_col]) for row in table.rows]
    axis_raw = [to_float(a, decimal) for a, _ in cells]
    values = [to_float(b, decimal) for _, b in cells]
    bad = sum(1 for (a, b), x, y in zip(cells, axis_raw, values, strict=True)
              if x is None or (y is None and not is_blank(b)))
    if bad:
        log.reject(item, "non_numeric",
                   f"{bad} linha(s) com comprimento de onda ou sinal inválido")
        return []
    identity = normalize_sample_id(resolved.raw or resolved.value)
    meta = (*merge_metadata(plan.sample_defaults, {}), dict(plan.spectrum_defaults))
    parsed = _finish(item, identity, resolved.origin, None, axis_raw,
                     [np.nan if v is None else v for v in values], plan, log, meta, thresholds)
    return [parsed] if parsed else []
