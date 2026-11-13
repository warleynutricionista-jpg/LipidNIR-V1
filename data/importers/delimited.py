"""CSV, TSV e TXT: detecção de codificação, delimitador, separador decimal e cabeçalho."""

from __future__ import annotations

import csv
import io
import re

from lipidence_modular.data.importers.table import (
    WHITESPACE,
    Detection,
    ImportFileError,
    RawTable,
    is_blank,
    to_float,
    unique_columns,
)

_CANDIDATES = (";", "\t", ",", "|")
_DECIMAL_COMMA = re.compile(r"^[+-]?\d+,\d+([eE][+-]?\d+)?$")
_SAMPLE_LINES = 50
VALID_DELIMITERS = (*_CANDIDATES, WHITESPACE)


def decode(content: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ImportFileError("codificação do arquivo não reconhecida (esperado UTF-8 ou CP1252)")


def detect_delimiter(lines: list[str]) -> str:
    """Delimitador presente o mesmo número de vezes (> 0) em todas as linhas da amostra.
    Ordem de preferência: ``;``, tabulação, ``,``, ``|``; por fim, espaços."""
    for candidate in _CANDIDATES:
        counts = {line.count(candidate) for line in lines}
        if len(counts) == 1 and counts != {0}:
            return candidate
    counts = {len(line.split()) for line in lines}
    if len(counts) == 1 and counts != {1}:
        return WHITESPACE
    # Sem consistência perfeita: o candidato mais frequente na primeira linha.
    best = max(_CANDIDATES, key=lambda c: lines[0].count(c))
    if lines[0].count(best) > 0:
        return best
    if len(lines[0].split()) > 1:
        return WHITESPACE
    raise ImportFileError("não foi possível detectar o delimitador; informe-o no mapeamento")


def split_rows(text: str, delimiter: str) -> list[list[str]]:
    if delimiter == WHITESPACE:
        return [line.split() for line in text.splitlines() if line.strip()]
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    return [[cell.strip() for cell in row] for row in reader if any(c.strip() for c in row)]


def detect_decimal(rows: list[list[str]], delimiter: str) -> str:
    if delimiter == ",":
        return "."
    for row in rows[:_SAMPLE_LINES]:
        if any(_DECIMAL_COMMA.match(cell) for cell in row):
            return ","
    return "."


def detect_header(rows: list[list[str]], decimal: str) -> bool:
    """Há cabeçalho quando a primeira linha tem alguma célula não numérica."""
    return any(not is_blank(c) and to_float(c, decimal) is None for c in rows[0])


def read_delimited(
    content: bytes,
    file_format: str,
    *,
    delimiter: str | None = None,
    decimal: str | None = None,
    has_header: bool | None = None,
) -> RawTable:
    text, encoding = decode(content)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ImportFileError("arquivo sem linhas de dados")
    if delimiter is not None and delimiter not in VALID_DELIMITERS:
        raise ImportFileError(
            f"delimitador não suportado: {delimiter!r}. Aceitos: {list(VALID_DELIMITERS)}"
        )
    if decimal is not None and decimal not in (".", ","):
        raise ImportFileError(f"separador decimal não suportado: {decimal!r}")
    delimiter = delimiter or detect_delimiter(lines[:_SAMPLE_LINES])
    if delimiter == "," and decimal == ",":
        raise ImportFileError("delimitador e separador decimal não podem ser ambos ','")
    rows = split_rows(text, delimiter)
    decimal = decimal or detect_decimal(rows, delimiter)
    header = detect_header(rows, decimal) if has_header is None else has_header
    width = max(len(row) for row in rows)
    notes = []
    if any(len(row) != width for row in rows):
        notes.append("linhas com número de colunas diferente foram completadas com vazio")
    rows = [row + [""] * (width - len(row)) for row in rows]
    if header:
        columns, body = unique_columns(rows[0]), rows[1:]
    else:
        columns, body = [f"col{i}" for i in range(1, width + 1)], rows
    if not body:
        raise ImportFileError("arquivo sem linhas de dados além do cabeçalho")
    detection = Detection(
        file_format=file_format, encoding=encoding, delimiter=delimiter, decimal=decimal,
        has_header=header,
    )
    return RawTable(columns=columns, rows=[list(r) for r in body], detection=detection,
                    notes=notes)
