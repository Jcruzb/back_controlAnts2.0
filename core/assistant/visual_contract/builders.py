from copy import deepcopy

from core.assistant.visual_contract.actions import validate_actions
from core.assistant.visual_contract.registry import validate_block


def build_block(block_type, **values):
    payload = {"type": block_type, **values}
    validate_block(payload)
    return deepcopy(payload)


def build_summary_card(**values):
    return build_block("summary_card", **values)


def build_metric_grid(**values):
    return build_block("metric_grid", **values)


def build_alert(**values):
    return build_block("alert", **values)


def build_simple_table(**values):
    return build_block("simple_table", **values)


def build_bar_chart(**values):
    return build_block("bar_chart", **values)


def build_line_chart(**values):
    return build_block("line_chart", **values)


def build_recommendation(**values):
    return build_block("recommendation", **values)


def build_question(**values):
    return build_block("question", **values)


def build_action_group(**values):
    if "actions" in values:
        validate_actions(values["actions"])
    return build_block("action_group", **values)
