from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import uuid

from django.conf import settings
from django.utils import timezone

from core.assistant.errors import (
    InvalidVisualBlockError,
    TooManyAlertsError,
    TooManyBlocksError,
)
from core.assistant.intents import validate_intent
from core.assistant.visual_contract.actions import validate_actions
from core.assistant.visual_contract.enums import (
    BlockType,
    MAX_BLOCKS,
    MAX_VISIBLE_ALERTS,
    ResponseSource,
    SCHEMA_VERSION,
)
from core.assistant.visual_contract.registry import validate_block
from core.assistant.visual_contract.validators import require_string


@dataclass(frozen=True)
class AssistantVisualResponse:
    intent: str
    summary: str
    blocks: List[Dict]
    period: Optional[Dict] = None
    actions: Optional[List[Dict]] = None
    has_more: bool = False
    request_id: Optional[str] = None
    response_id: Optional[str] = None
    source: str = ResponseSource.DETERMINISTIC.value
    generated_at: Optional[datetime] = None

    def to_dict(self):
        validate_intent(self.intent)
        require_string(self.summary, field="summary", maximum=180)
        if self.source not in ResponseSource.values():
            raise InvalidVisualBlockError(details={"field": "source"})
        if not isinstance(self.blocks, list) or len(self.blocks) > MAX_BLOCKS:
            raise TooManyBlocksError()

        ids = set()
        summary_positions = []
        alert_count = 0
        question_count = 0
        for index, block in enumerate(self.blocks):
            validate_block(block)
            block_id = block["id"]
            if block_id in ids:
                raise InvalidVisualBlockError(details={"field": "blocks.id"})
            ids.add(block_id)
            if block["type"] == BlockType.SUMMARY_CARD.value:
                summary_positions.append(index)
            elif block["type"] == BlockType.ALERT.value:
                alert_count += 1
            elif block["type"] == BlockType.QUESTION.value:
                question_count += 1
            if self.source == ResponseSource.DETERMINISTIC.value and block["type"] in {
                BlockType.RECOMMENDATION.value,
                BlockType.QUESTION.value,
            }:
                raise InvalidVisualBlockError(details={"field": "blocks.type"})
        if len(summary_positions) > 1 or (summary_positions and summary_positions[0] != 0):
            raise InvalidVisualBlockError(details={"field": "blocks.summary_card"})
        if alert_count > MAX_VISIBLE_ALERTS:
            raise TooManyAlertsError()
        if question_count > 1:
            raise InvalidVisualBlockError(details={"field": "blocks.question"})

        if self.actions is not None:
            validate_actions(self.actions)
        if self.period is not None:
            self._validate_period(self.period)

        generated_at = self.generated_at or timezone.localtime(
            timezone.now(), timezone.get_default_timezone()
        )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "response_id": self.response_id or f"resp_{uuid.uuid4()}",
            "source": self.source,
            "intent": self.intent,
            "summary": self.summary,
            "blocks": self.blocks,
            "meta": {
                "has_more": bool(self.has_more),
                "generated_at": generated_at.isoformat(),
                "request_id": self.request_id or f"req_{uuid.uuid4()}",
            },
        }
        if self.period is not None:
            payload["period"] = self.period
        if self.actions is not None:
            payload["actions"] = self.actions
        return payload

    @staticmethod
    def _validate_period(period):
        if not isinstance(period, dict) or set(period) != {"year", "month", "label", "timezone"}:
            raise InvalidVisualBlockError(details={"field": "period"})
        year = period["year"]
        month = period["month"]
        if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
            raise InvalidVisualBlockError(details={"field": "period.year"})
        if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
            raise InvalidVisualBlockError(details={"field": "period.month"})
        require_string(period["label"], field="period.label", maximum=40)
        if period["timezone"] != settings.TIME_ZONE:
            raise InvalidVisualBlockError(details={"field": "period.timezone"})
