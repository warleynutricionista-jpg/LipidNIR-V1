"""Problemas encontrados na importação e o relatório final (seção 8.7)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class IssueLevel(enum.StrEnum):
    ALERT = "ALERT"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ItemIssue:
    item: str
    level: IssueLevel
    code: str
    message: str


@dataclass
class IssueLog:
    """Acumula problemas por item. Um item é uma unidade do arquivo: uma linha (layout
    largo, combinado ou referência) ou uma amostra (layout longo e arquivo único)."""

    items: list[str] = field(default_factory=list)
    issues: list[ItemIssue] = field(default_factory=list)

    def register(self, item: str) -> None:
        if item not in self.items:
            self.items.append(item)

    def _add(self, issue: ItemIssue) -> None:
        """O mesmo problema do mesmo item entra uma vez só (o arquivo combinado passa
        pelos dois interpretadores)."""
        self.register(issue.item)
        if issue not in self.issues:
            self.issues.append(issue)

    def alert(self, item: str, code: str, message: str) -> None:
        self._add(ItemIssue(item, IssueLevel.ALERT, code, message))

    def reject(self, item: str, code: str, message: str) -> None:
        self._add(ItemIssue(item, IssueLevel.REJECTED, code, message))

    def is_rejected(self, item: str) -> bool:
        return any(i.item == item and i.level is IssueLevel.REJECTED for i in self.issues)

    def has_alert(self, item: str) -> bool:
        return any(i.item == item and i.level is IssueLevel.ALERT for i in self.issues)

    def counts(self) -> dict[str, int]:
        """Contagens mutuamente exclusivas: recebidos = importados + alertas + rejeitados."""
        rejected = sum(1 for item in self.items if self.is_rejected(item))
        alerts = sum(
            1 for item in self.items if not self.is_rejected(item) and self.has_alert(item)
        )
        return {
            "received": len(self.items),
            "imported": len(self.items) - rejected - alerts,
            "alerts": alerts,
            "rejected": rejected,
        }
