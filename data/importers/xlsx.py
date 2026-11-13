"""XLSX (openpyxl). Células numéricas chegam como número; não há separador decimal."""

from __future__ import annotations

import io

from lipidence_modular.data.importers.table import (
    Detection,
    ImportFileError,
    RawTable,
    is_blank,
    to_float,
    unique_columns,
)


def read_xlsx(content: bytes, *, has_header: bool | None = None,
              sheet: str | None = None) -> RawTable:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ImportFileError(f"planilha XLSX ilegível: {exc}") from exc
    try:
        names = tuple(workbook.sheetnames)
        if sheet is not None and sheet not in names:
            raise ImportFileError(f"aba {sheet!r} não existe. Abas: {list(names)}")
        worksheet = workbook[sheet] if sheet else workbook[names[0]]
        rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    finally:
        workbook.close()
    rows = [row for row in rows if any(not is_blank(cell) for cell in row)]
    if not rows:
        raise ImportFileError("planilha sem dados")
    width = max(len(row) for row in rows)
    while width and all(is_blank(row[width - 1]) if len(row) >= width else True for row in rows):
        width -= 1
    rows = [(row + [None] * width)[:width] for row in rows]
    header = (
        any(not is_blank(c) and to_float(c) is None for c in rows[0])
        if has_header is None else has_header
    )
    if header:
        columns, body = unique_columns([_header_text(c) for c in rows[0]]), rows[1:]
    else:
        columns, body = [f"col{i}" for i in range(1, width + 1)], rows
    if not body:
        raise ImportFileError("planilha sem linhas de dados além do cabeçalho")
    notes = [] if len(names) == 1 else [f"planilha com {len(names)} abas; lida: {worksheet.title}"]
    detection = Detection(file_format="xlsx", has_header=header, sheet=worksheet.title,
                          sheets=names)
    return RawTable(columns=columns, rows=body, detection=detection, notes=notes)


def _header_text(cell: object) -> object:
    """Cabeçalho numérico de planilha (comprimento de onda) sem o ``.0`` artificial."""
    if isinstance(cell, float) and cell.is_integer():
        return str(int(cell))
    return cell
