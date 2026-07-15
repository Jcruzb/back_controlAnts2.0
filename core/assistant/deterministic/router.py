from dataclasses import dataclass
import re

from core.assistant.visual_contract.enums import Confidence
from core.assistant.deterministic.normalizer import normalize_text, resolve_period


@dataclass(frozen=True)
class MatchResult:
    intent: str = None
    confidence: str = Confidence.NONE.value
    arguments: dict = None
    normalized_message: str = ""

    @property
    def can_respond(self):
        return self.confidence == Confidence.HIGH.value and self.intent is not None


INTENT_PATTERNS = (
    (
        "payer_spending",
        (
            r"cuanto (?:ha )?pag(?:o|ado) cada persona",
            r"cuanto (?:ha )?pag(?:o|ado) cada (?:uno|pagador)",
            r"gasto por (?:persona|pagador)",
            r"quien (?:ha )?pagado",
        ),
    ),
    (
        "category_spending",
        (
            r"en que categoria gastamos mas",
            r"categoria con (?:mas|mayor) gasto",
            r"gasto por categoria",
            r"categorias? (?:gastamos|gasto)",
        ),
    ),
    (
        "pending_payments",
        (
            r"que pagos? faltan",
            r"pagos? pendientes?",
            r"cuanto queda pendiente",
            r"que queda pendiente",
        ),
    ),
    (
        "monthly_cash_balance",
        (
            r"cuanto dinero (?:me|nos)? ?queda",
            r"balance (?:real|de caja)",
            r"saldo de caja",
        ),
    ),
    (
        "monthly_spending",
        (
            r"cuanto (?:hemos|he) gastado",
            r"gasto total",
            r"cuanto se ha gastado",
        ),
    ),
    (
        "monthly_summary",
        (
            r"como vamos",
            r"resumen (?:del|de este) mes",
            r"como esta (?:el )?presupuesto",
            r"estado (?:del mes|de [a-z]+)",
            r"situacion (?:general|del mes|economica)",
        ),
    ),
)


class DeterministicIntentRouter:
    def match(self, message, *, reference_date=None):
        normalized = normalize_text(message)
        for intent, patterns in INTENT_PATTERNS:
            if any(re.search(pattern, normalized) for pattern in patterns):
                period = resolve_period(message, reference_date=reference_date)
                return MatchResult(
                    intent=intent,
                    confidence=Confidence.HIGH.value,
                    arguments={"year": period.year, "month": period.month},
                    normalized_message=normalized,
                )

        weak_tokens = {"presupuesto", "gastos", "pagos", "categorias", "pagadores", "balance"}
        if weak_tokens.intersection(normalized.split()):
            return MatchResult(
                confidence=Confidence.MEDIUM.value,
                arguments={},
                normalized_message=normalized,
            )
        return MatchResult(
            confidence=Confidence.NONE.value,
            arguments={},
            normalized_message=normalized,
        )
