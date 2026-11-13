"""Interpretação de análises de referência: formato longo (uma linha por medida) e largo
(uma coluna por parâmetro). Usa o vocabulário controlado; nada fora dele entra sem
mapeamento confirmado no plano (INV-7)."""

from __future__ import annotations

from collections import defaultdict

from lipidence_modular.data.identity.resolution import FieldOrigin
from lipidence_modular.data.importers.table import RawTable, is_blank, to_float
from lipidence_modular.data.ingestion.plan import ImportPlan
from lipidence_modular.data.ingestion.spectra import (
    PlanError,
    _identity_from_cell,
    _prefixed,
    _single_role,
    merge_metadata,
    row_metadata,
)
from lipidence_modular.data.mapping import roles
from lipidence_modular.data.reference.vocabulary import ParameterSpec, Vocabulary
from lipidence_modular.data.schemas.issues import IssueLog
from lipidence_modular.data.schemas.reference import ParsedReference


def has_reference_columns(mapping: dict[str, str]) -> bool:
    assigned = list(mapping.values())
    return (roles.PARAMETER in assigned and roles.VALUE in assigned) or any(
        role.startswith(roles.REFERENCE_PREFIX) for role in assigned
    )


def _resolve_parameter(raw: object, plan: ImportPlan, vocabulary: Vocabulary):
    text = str(raw).strip()
    mapped = plan.parameter_map.get(text, text)
    return vocabulary.resolve_parameter(mapped)


def _resolve_unit(raw: object | None, spec: ParameterSpec, plan: ImportPlan,
                  vocabulary: Vocabulary) -> tuple[str | None, str | None]:
    """(unidade aceita, mensagem de erro)."""
    if raw is None or is_blank(raw):
        return None, f"{spec.name}: referência sem unidade"
    text = " ".join(str(raw).split())
    unit = vocabulary.resolve_unit(spec, plan.unit_map.get(text, text))
    if unit is None:
        return None, (f"{spec.name}: unidade desconhecida {text!r} "
                      f"(aceitas: {', '.join(spec.units)})")
    return unit, None


def _replicate(cell: object, decimal: str) -> tuple[int | None, bool]:
    if is_blank(cell):
        return None, True
    number = to_float(cell, decimal)
    if number is None or number < 1 or not float(number).is_integer():
        return None, False
    return int(number), True


def _apply_duplicate_policy(references: list[ParsedReference], plan: ImportPlan,
                            log: IssueLog) -> list[ParsedReference]:
    groups: dict[tuple[str, str], list[ParsedReference]] = defaultdict(list)
    for ref in references:
        groups[(ref.sample_id, ref.parameter)].append(ref)
    kept: list[ParsedReference] = []
    for (sample_id, parameter), group in groups.items():
        explicit = [r.replicate for r in group if r.replicate is not None]
        label = f"{sample_id} / {parameter}"
        if len(group) == 1:
            kept.extend(group)
        elif len(explicit) == len(group):
            if len(set(explicit)) != len(explicit):
                for r in group:
                    log.reject(r.item, "duplicate_replicate", f"{label}: replicata repetida")
            else:
                kept.extend(group)
        elif explicit:
            for r in group:
                log.reject(r.item, "replicate_partial",
                           f"{label}: replicata informada só em parte das linhas")
        elif plan.repeated_rows_are_replicates:
            for number, r in enumerate(group, start=1):
                r.replicate = number
            kept.extend(group)
        else:
            for r in group:
                log.reject(r.item, "duplicate_measurement",
                           f"{label}: medida duplicada sem replicata declarada")
    return kept


def parse_reference(table: RawTable, mapping: dict[str, str], plan: ImportPlan,
                    vocabulary: Vocabulary, log: IssueLog) -> list[ParsedReference]:
    """Medidas válidas do arquivo. O que foi rejeitado fica só no ``log``."""
    decimal = table.detection.decimal
    id_column = _single_role(mapping, roles.SAMPLE_ID)
    if id_column is None:
        raise PlanError("análises de referência exigem uma coluna mapeada como sample_id")
    id_col = table.column_index(id_column)
    sample_cols = _prefixed(mapping, roles.META_PREFIX)
    field_cols = {role: _single_role(mapping, role) for role in roles.REFERENCE_FIELDS}
    parameter_col = _single_role(mapping, roles.PARAMETER)
    value_col = _single_role(mapping, roles.VALUE)
    unit_col = _single_role(mapping, roles.UNIT)
    wide_cols = _prefixed(mapping, roles.REFERENCE_PREFIX)
    long_layout = parameter_col is not None and value_col is not None
    if long_layout and wide_cols:
        raise PlanError("mapeamento mistura referência em formato longo e largo")
    if not long_layout and not wide_cols:
        raise PlanError(
            "nenhuma coluna de referência: mapeie parameter + value (longo) ou "
            "reference:<parâmetro> (largo)"
        )

    def text(row, column):
        if column is None or is_blank(row[table.column_index(column)]):
            return None
        return str(row[table.column_index(column)]).strip()

    def field_value(row, name):
        return text(row, field_cols[name]) or plan.reference_defaults.get(name)

    references: list[ParsedReference] = []
    for number, row in enumerate(table.rows, start=1):
        identity = _identity_from_cell(row[id_col], f"linha {number}", log)
        if identity is None:
            continue
        item = f"{identity.sample_id} (linha {number})"
        log.register(item)
        replicate, ok = (None, True)
        if field_cols["replicate"] is not None:
            replicate, ok = _replicate(row[table.column_index(field_cols["replicate"])], decimal)
        if not ok:
            log.reject(item, "replicate_invalid", "replicata deve ser inteiro ≥ 1")
            continue
        sample_meta, origins = merge_metadata(
            plan.sample_defaults, row_metadata(table, row, sample_cols)
        )

        if long_layout:
            raw_parameter = text(row, parameter_col)
            measures = [(raw_parameter, row[table.column_index(value_col)],
                         text(row, unit_col) if unit_col else None, None)]
        else:
            measures = []
            for column, parameter in wide_cols.items():
                cell = row[table.column_index(column)]
                if is_blank(cell):
                    continue  # amostra sem esse parâmetro: não é erro, só não há medida
                header_unit = roles.split_header_unit(column)[1]
                measures.append((parameter, cell, header_unit, parameter))
            if not measures:
                log.reject(item, "no_values", "linha sem nenhum valor de referência")
                continue

        produced = 0
        for raw_parameter, cell, unit_raw, known in measures:
            if raw_parameter is None:
                log.reject(item, "parameter_missing", "parâmetro ausente")
                continue
            spec = vocabulary.parameters[known] if known else _resolve_parameter(
                raw_parameter, plan, vocabulary
            )
            if spec is None:
                log.reject(item, "parameter_unknown",
                           f"parâmetro fora do vocabulário: {raw_parameter!r}")
                continue
            value = to_float(cell, decimal)
            if value is None:
                log.reject(item, "non_numeric", f"{spec.name}: valor não numérico")
                continue
            unit, error = _resolve_unit(
                unit_raw if unit_raw is not None else plan.reference_units.get(spec.name),
                spec, plan, vocabulary,
            )
            if error:
                log.reject(item, "unit", error)
                continue
            if not spec.in_plausible_range(value):
                log.alert(item, "implausible_value",
                          f"{spec.name} = {value:g} {unit} fora da faixa plausível (PROVISORIO)")
            references.append(ParsedReference(
                item=item, sample_id=identity.sample_id, sample_id_raw=identity.sample_id_raw,
                sample_id_origin=FieldOrigin.FILE, parameter=spec.name, value=value, unit=unit,
                replicate=replicate,
                analysis_type=field_value(row, "analysis_type") or spec.analysis_type,
                method=field_value(row, "method"), date=field_value(row, "date"),
                laboratory=field_value(row, "laboratory"), sample_metadata=sample_meta,
                metadata_origins=origins,
            ))
            produced += 1
        # Linha larga com parte das medidas rejeitada: as válidas não entram sozinhas,
        # para que "rejeitado" signifique sempre "nada desta linha foi importado".
        if log.is_rejected(item) and produced:
            del references[-produced:]
    return _apply_duplicate_policy(references, plan, log)

