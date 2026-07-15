from copy import deepcopy

from core.assistant.errors import InvalidActionError, UnsupportedIntentError
from core.assistant.intents import validate_intent
from core.assistant.visual_contract.enums import (
    ActionStyle,
    ActionType,
    MAX_ACTIONS,
)
from core.assistant.visual_contract.validators import (
    reject_unknown_fields,
    require_enum,
    require_fields,
    require_id,
    require_mapping,
    require_string,
)


# Verified against front-controlAnts2.0/src/app/Router.jsx.
NAVIGATION_ALLOWLIST = frozenset({
    "/",
    "/dashboard",
    "/expenses",
    "/incomes",
    "/recurring",
    "/categories",
    "/account",
})

READ_ONLY_ACTION_TYPES = frozenset({
    ActionType.FETCH_DETAIL.value,
    ActionType.NAVIGATE.value,
    ActionType.SEND_INTENT.value,
    ActionType.SUBMIT_ANSWER.value,
    ActionType.EXPAND.value,
    ActionType.COLLAPSE.value,
})


def validate_action(payload, *, require_id_field=True):
    require_mapping(payload, field="action", error_type=InvalidActionError)
    required = {"type", "label"}
    if require_id_field:
        required.add("id")
    require_fields(payload, required=required, error_type=InvalidActionError)
    reject_unknown_fields(
        payload,
        allowed={"id", "type", "label", "intent", "arguments", "target", "style"},
        error_type=InvalidActionError,
    )
    if require_id_field:
        require_id(payload["id"], field="id", error_type=InvalidActionError)
    action_type = require_enum(payload["type"], ActionType, field="type", error_type=InvalidActionError)
    if action_type not in READ_ONLY_ACTION_TYPES:
        raise InvalidActionError(details={"field": "type"})
    require_string(payload["label"], field="label", maximum=50, error_type=InvalidActionError)
    style = payload.get("style", ActionStyle.SECONDARY.value)
    require_enum(style, ActionStyle, field="style", error_type=InvalidActionError)
    if style == ActionStyle.DANGER.value:
        raise InvalidActionError(details={"field": "style"})

    if action_type == ActionType.NAVIGATE.value:
        target = require_string(payload.get("target"), field="target", maximum=80, error_type=InvalidActionError)
        if target not in NAVIGATION_ALLOWLIST:
            raise InvalidActionError(details={"field": "target"})
        if "intent" in payload or "arguments" in payload:
            raise InvalidActionError(details={"field": "intent"})
    elif action_type in {ActionType.FETCH_DETAIL.value, ActionType.SEND_INTENT.value}:
        try:
            validate_intent(payload.get("intent"))
        except UnsupportedIntentError:
            raise InvalidActionError(details={"field": "intent"})
        arguments = require_mapping(payload.get("arguments", {}), field="arguments", error_type=InvalidActionError)
        if set(arguments).difference({"year", "month"}):
            raise InvalidActionError(details={"field": "arguments"})
        year = arguments.get("year")
        month = arguments.get("month")
        if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
            raise InvalidActionError(details={"field": "arguments.year"})
        if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
            raise InvalidActionError(details={"field": "arguments.month"})
    elif action_type == ActionType.SUBMIT_ANSWER.value:
        if "target" in payload:
            raise InvalidActionError(details={"field": "target"})
    elif any(field in payload for field in ("intent", "arguments", "target")):
        raise InvalidActionError(details={"field": "intent"})
    return payload


def validate_actions(actions):
    if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_ACTIONS:
        raise InvalidActionError(details={"field": "actions"})
    ids = set()
    primary_count = 0
    for action in actions:
        validate_action(action)
        if action["id"] in ids:
            raise InvalidActionError(details={"field": "id"})
        ids.add(action["id"])
        if action.get("style") == ActionStyle.PRIMARY.value:
            primary_count += 1
    if primary_count > 1:
        raise InvalidActionError(details={"field": "style"})
    return actions


def build_action(**values):
    payload = {key: value for key, value in values.items() if value is not None}
    validate_action(payload)
    return deepcopy(payload)
