"""Tabela bruta e detecção de formato.

# Portado de backend/app/services/file_parser.py@e027e41 (_parse_tabular, _parse_excel,
# parse_file_preview): leitura e preview de CSV/TXT/XLSX. Adaptações: a detecção de
# delimitador, separador decimal e cabeçalho é explícita e devolvida para confirmação;
# JCAMP-DX e SPA não foram portados (adapters futuros).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from lipidence_modular.core.errors import LipidenceError

SUPPORTED_EXTENSIONS = ("csv", "tsv", "txt", "xlsx")
_NUMERIC_DOT = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_NUMERIC_COMMA = re.compile(r"^[+-]?(\d+,?\d*|,\d+)([eE][+-]?\d+)?$")
WHITESPACE = "whitespace"


class ImportFileError(LipidenceError):
    """Arquivo ilegível, vazio ou de formato não suportado."""


@dataclass(frozen=True)
class Detection:
    file_format: str
    encoding: str | None = None
    delimiter: str | None = None
    decimal: str = "."
    has_header: bool = True
    sheet: str | None = None
    sheets: tuple[str, ...] = ()


@dataclass
class RawTable:
    columns: list[str]
    rows: list[list[object]]
    detection: Detection
    notes: list[str] = field(default_factory=list)

    def column_index(self, name: str) -> int:
        return self.columns.index(name)


def to_float(cell: object, decimal: str = ".") -> float | None:
    """Número da célula, ou ``None`` quando vazia ou não numérica. Nunca adivinha."""
    if cell is None or isinstance(cell, bool):
        return None
    if isinstance(cell, int | float):
        value = float(cell)
        return value if value == value and abs(value) != float("inf") else None
    text = str(cell).strip()
    if not text:
        return None
    if decimal == ",":
        if not _NUMERIC_COMMA.match(text):
            return None
        text = text.replace(",", ".")
    elif not _NUMERIC_DOT.match(text):
        return None
    return float(text)


def is_blank(cell: object) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip()) or (
        isinstance(cell, float) and cell != cell
    )


def extension_of(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise ImportFileError(
            f"formato não suportado: {filename!r}. Aceitos: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    return ext


def unique_columns(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for position, raw in enumerate(names, start=1):
        name = str(raw).strip() if not is_blank(raw) else f"col{position}"
        if name in seen:
            seen[name] += 1
            name = f"{name}#{seen[name]}"
        else:
            seen[name] = 1
        result.append(name)
    return result


def read_table(
    content: bytes,
    filename: str,
    *,
    delimiter: str | None = None,
    decimal: str | None = None,
    has_header: bool | None = None,
    sheet: str | None = None,
) -> RawTable:
    """Lê o arquivo. Parâmetros informados substituem a detecção automática."""
    ext = extension_of(filename)
    if not content:
        raise ImportFileError("arquivo vazio")
    if ext == "xlsx":
        from lipidence_modular.data.importers.xlsx import read_xlsx

        return read_xlsx(content, has_header=has_header, sheet=sheet)
    from lipidence_modular.data.importers.delimited import read_delimited

    return read_delimited(
        io.BytesIO(content).getvalue(), ext, delimiter=delimiter, decimal=decimal,
        has_header=has_header,
    )
