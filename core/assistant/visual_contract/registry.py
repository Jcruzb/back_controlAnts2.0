from types import MappingProxyType

from core.assistant.errors import UnsupportedBlockTypeError
from core.assistant.visual_contract.blocks import (
    ActionGroupBlock,
    AlertBlock,
    BarChartBlock,
    LineChartBlock,
    MetricGridBlock,
    QuestionBlock,
    RecommendationBlock,
    SimpleTableBlock,
    SummaryCardBlock,
)


BLOCK_REGISTRY = MappingProxyType({
    "summary_card": SummaryCardBlock,
    "metric_grid": MetricGridBlock,
    "alert": AlertBlock,
    "simple_table": SimpleTableBlock,
    "bar_chart": BarChartBlock,
    "line_chart": LineChartBlock,
    "recommendation": RecommendationBlock,
    "question": QuestionBlock,
    "action_group": ActionGroupBlock,
})


def get_block_class(block_type):
    try:
        return BLOCK_REGISTRY[block_type]
    except KeyError:
        raise UnsupportedBlockTypeError(details={"type": block_type})


def validate_block(payload):
    if not isinstance(payload, dict):
        raise UnsupportedBlockTypeError()
    block_class = get_block_class(payload.get("type"))
    block_class.validate(payload)
    return payload
