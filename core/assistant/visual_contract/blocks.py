import re

from core.assistant.dto import SPANISH_MONTH_NAMES
from core.assistant.errors import (
    InvalidChartError,
    InvalidTableError,
    InvalidVisualBlockError,
)
from core.assistant.visual_contract.base import VisualBlock
from core.assistant.visual_contract.enums import (
    ActionLayout,
    AlertSeverity,
    Alignment,
    BlockType,
    Confidence,
    DataKind,
    MAX_ACTIONS,
    MAX_BAR_CATEGORIES,
    MAX_BAR_SERIES,
    MAX_LINE_SERIES,
    MAX_METRICS,
    MAX_TABLE_COLUMNS,
    MAX_TABLE_ROWS,
    MIN_METRICS,
    QuestionInputType,
    RecommendationLevel,
    Status,
    TableFormat,
    TrendDirection,
    TrendMeaning,
)
from core.assistant.visual_contract.validators import (
    reject_unknown_fields,
    require_decimal_string,
    require_enum,
    require_fields,
    require_id,
    require_list,
    require_mapping,
    require_string,
)


def _validate_type(payload, expected):
    require_mapping(payload)
    if payload.get("type") != expected:
        raise InvalidVisualBlockError(details={"field": "type"})


class SummaryCardBlock(VisualBlock):
    block_type = BlockType.SUMMARY_CARD.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "title", "headline", "status"})
        reject_unknown_fields(
            payload,
            allowed={"type", "id", "title", "headline", "description", "status"},
        )
        require_id(payload["id"])
        require_string(payload["title"], field="title", maximum=60)
        require_string(payload["headline"], field="headline", maximum=90)
        if "description" in payload:
            require_string(payload["description"], field="description", maximum=180)
        require_enum(payload["status"], Status, field="status")


class MetricGridBlock(VisualBlock):
    block_type = BlockType.METRIC_GRID.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "items"})
        reject_unknown_fields(payload, allowed={"type", "id", "items"})
        require_id(payload["id"])
        items = require_list(payload["items"], field="items")
        if not MIN_METRICS <= len(items) <= MAX_METRICS:
            raise InvalidVisualBlockError(details={"field": "items"})
        keys = set()
        for index, item in enumerate(items):
            field = f"items.{index}"
            require_mapping(item, field=field)
            require_fields(item, required={"key", "label", "value", "formatted_value"})
            reject_unknown_fields(
                item,
                allowed={"key", "label", "value", "formatted_value", "status", "help_text", "trend"},
            )
            key = require_id(item["key"], field=f"{field}.key")
            if key in keys:
                raise InvalidVisualBlockError(details={"field": f"{field}.key"})
            keys.add(key)
            require_string(item["label"], field=f"{field}.label", maximum=40)
            require_decimal_string(item["value"], field=f"{field}.value")
            require_string(item["formatted_value"], field=f"{field}.formatted_value", maximum=40)
            if "status" in item:
                require_enum(item["status"], Status, field=f"{field}.status")
            if "help_text" in item:
                require_string(item["help_text"], field=f"{field}.help_text", maximum=140)
            if "trend" in item:
                cls._validate_trend(item["trend"], field=f"{field}.trend")

    @staticmethod
    def _validate_trend(trend, *, field):
        require_mapping(trend, field=field)
        require_fields(
            trend,
            required={"direction", "value", "formatted_value", "comparison_label", "meaning"},
        )
        reject_unknown_fields(
            trend,
            allowed={"direction", "value", "formatted_value", "comparison_label", "meaning"},
        )
        require_enum(trend["direction"], TrendDirection, field=f"{field}.direction")
        require_decimal_string(trend["value"], field=f"{field}.value")
        require_string(trend["formatted_value"], field=f"{field}.formatted_value", maximum=40)
        require_string(trend["comparison_label"], field=f"{field}.comparison_label", maximum=90)
        require_enum(trend["meaning"], TrendMeaning, field=f"{field}.meaning")


class AlertBlock(VisualBlock):
    block_type = BlockType.ALERT.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "code", "severity", "title", "message", "facts"})
        reject_unknown_fields(
            payload,
            allowed={"type", "id", "code", "severity", "title", "message", "facts", "action"},
        )
        require_id(payload["id"])
        require_id(payload["code"], field="code")
        require_enum(payload["severity"], AlertSeverity, field="severity")
        require_string(payload["title"], field="title", maximum=90)
        require_string(payload["message"], field="message", maximum=180)
        facts = require_mapping(payload["facts"], field="facts")
        if len(facts) > 6:
            raise InvalidVisualBlockError(details={"field": "facts"})
        for key, value in facts.items():
            require_id(key, field="facts.key")
            if not isinstance(value, (str, int, bool)) or isinstance(value, float):
                raise InvalidVisualBlockError(details={"field": f"facts.{key}"})
        if "action" in payload:
            from core.assistant.visual_contract.actions import validate_action

            validate_action(payload["action"], require_id_field=False)


class SimpleTableBlock(VisualBlock):
    block_type = BlockType.SIMPLE_TABLE.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(
            payload,
            required={"type", "id", "title", "columns", "rows", "limit", "total_rows", "has_more"},
            error_type=InvalidTableError,
        )
        reject_unknown_fields(
            payload,
            allowed={"type", "id", "title", "description", "columns", "rows", "limit", "total_rows", "has_more"},
            error_type=InvalidTableError,
        )
        require_id(payload["id"], error_type=InvalidTableError)
        require_string(payload["title"], field="title", maximum=80, error_type=InvalidTableError)
        if "description" in payload:
            require_string(payload["description"], field="description", maximum=180, error_type=InvalidTableError)
        columns = require_list(payload["columns"], field="columns", error_type=InvalidTableError)
        rows = require_list(payload["rows"], field="rows", error_type=InvalidTableError)
        if not 1 <= len(columns) <= MAX_TABLE_COLUMNS or len(rows) > MAX_TABLE_ROWS:
            raise InvalidTableError()
        column_keys = []
        formats = {}
        for index, column in enumerate(columns):
            field = f"columns.{index}"
            require_mapping(column, field=field, error_type=InvalidTableError)
            require_fields(column, required={"key", "label", "format", "align"}, error_type=InvalidTableError)
            reject_unknown_fields(column, allowed={"key", "label", "format", "align"}, error_type=InvalidTableError)
            key = require_id(column["key"], field=f"{field}.key", error_type=InvalidTableError)
            if key in column_keys:
                raise InvalidTableError(details={"field": f"{field}.key"})
            column_keys.append(key)
            formats[key] = column["format"]
            require_string(column["label"], field=f"{field}.label", maximum=40, error_type=InvalidTableError)
            require_enum(column["format"], TableFormat, field=f"{field}.format", error_type=InvalidTableError)
            require_enum(column["align"], Alignment, field=f"{field}.align", error_type=InvalidTableError)
        for index, row in enumerate(rows):
            field = f"rows.{index}"
            require_mapping(row, field=field, error_type=InvalidTableError)
            require_id(row.get("id"), field=f"{field}.id", error_type=InvalidTableError)
            for key in column_keys:
                if key not in row:
                    raise InvalidTableError(details={"field": f"{field}.{key}"})
                if formats[key] in {TableFormat.CURRENCY.value, TableFormat.PERCENTAGE.value}:
                    require_decimal_string(row[key], field=f"{field}.{key}", error_type=InvalidTableError)
        for key in column_keys:
            if rows and all(row.get(key) in (None, "") for row in rows):
                raise InvalidTableError(details={"field": f"columns.{key}"})
        if not isinstance(payload["limit"], int) or not 1 <= payload["limit"] <= MAX_TABLE_ROWS:
            raise InvalidTableError(details={"field": "limit"})
        if not isinstance(payload["total_rows"], int) or payload["total_rows"] < len(rows):
            raise InvalidTableError(details={"field": "total_rows"})
        if not isinstance(payload["has_more"], bool):
            raise InvalidTableError(details={"field": "has_more"})


def _validate_axis(axis, *, field, error_type):
    require_mapping(axis, field=field, error_type=error_type)
    require_fields(axis, required={"key", "label"}, error_type=error_type)
    reject_unknown_fields(axis, allowed={"key", "label"}, error_type=error_type)
    require_id(axis["key"], field=f"{field}.key", error_type=error_type)
    require_string(axis["label"], field=f"{field}.label", maximum=40, error_type=error_type)


class BarChartBlock(VisualBlock):
    block_type = BlockType.BAR_CHART.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "title", "explanation", "x_axis", "series", "data"}, error_type=InvalidChartError)
        reject_unknown_fields(payload, allowed={"type", "id", "title", "explanation", "x_axis", "series", "data"}, error_type=InvalidChartError)
        require_id(payload["id"], error_type=InvalidChartError)
        require_string(payload["title"], field="title", maximum=80, error_type=InvalidChartError)
        require_string(payload["explanation"], field="explanation", maximum=180, error_type=InvalidChartError)
        _validate_axis(payload["x_axis"], field="x_axis", error_type=InvalidChartError)
        series = require_list(payload["series"], field="series", error_type=InvalidChartError)
        data = require_list(payload["data"], field="data", error_type=InvalidChartError)
        if not 1 <= len(series) <= MAX_BAR_SERIES or not 1 <= len(data) <= MAX_BAR_CATEGORIES:
            raise InvalidChartError()
        cls._validate_series_and_data(series, data, payload["x_axis"]["key"])

    @staticmethod
    def _validate_series_and_data(series, data, axis_key):
        keys = []
        for index, item in enumerate(series):
            field = f"series.{index}"
            require_mapping(item, field=field, error_type=InvalidChartError)
            require_fields(item, required={"key", "label", "format"}, error_type=InvalidChartError)
            reject_unknown_fields(item, allowed={"key", "label", "format"}, error_type=InvalidChartError)
            keys.append(require_id(item["key"], field=f"{field}.key", error_type=InvalidChartError))
            require_string(item["label"], field=f"{field}.label", maximum=40, error_type=InvalidChartError)
            require_enum(item["format"], TableFormat, field=f"{field}.format", error_type=InvalidChartError)
        for row_index, row in enumerate(data):
            require_mapping(row, field=f"data.{row_index}", error_type=InvalidChartError)
            if axis_key not in row:
                raise InvalidChartError(details={"field": f"data.{row_index}.{axis_key}"})
            for key in keys:
                require_decimal_string(row.get(key), field=f"data.{row_index}.{key}", error_type=InvalidChartError)


class LineChartBlock(VisualBlock):
    block_type = BlockType.LINE_CHART.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "title", "explanation", "x_axis", "series", "data"}, error_type=InvalidChartError)
        reject_unknown_fields(payload, allowed={"type", "id", "title", "explanation", "x_axis", "series", "data"}, error_type=InvalidChartError)
        require_id(payload["id"], error_type=InvalidChartError)
        require_string(payload["title"], field="title", maximum=80, error_type=InvalidChartError)
        require_string(payload["explanation"], field="explanation", maximum=180, error_type=InvalidChartError)
        _validate_axis(payload["x_axis"], field="x_axis", error_type=InvalidChartError)
        series = require_list(payload["series"], field="series", error_type=InvalidChartError)
        data = require_list(payload["data"], field="data", error_type=InvalidChartError)
        if not 1 <= len(series) <= MAX_LINE_SERIES or len(data) < 2:
            raise InvalidChartError()
        keys = []
        for index, item in enumerate(series):
            field = f"series.{index}"
            require_mapping(item, field=field, error_type=InvalidChartError)
            require_fields(item, required={"key", "label", "format", "data_kind"}, error_type=InvalidChartError)
            reject_unknown_fields(item, allowed={"key", "label", "format", "data_kind"}, error_type=InvalidChartError)
            keys.append(require_id(item["key"], field=f"{field}.key", error_type=InvalidChartError))
            require_string(item["label"], field=f"{field}.label", maximum=40, error_type=InvalidChartError)
            require_enum(item["format"], TableFormat, field=f"{field}.format", error_type=InvalidChartError)
            require_enum(item["data_kind"], DataKind, field=f"{field}.data_kind", error_type=InvalidChartError)
        axis_key = payload["x_axis"]["key"]
        periods = []
        for row_index, row in enumerate(data):
            require_mapping(row, field=f"data.{row_index}", error_type=InvalidChartError)
            period = require_string(row.get(axis_key), field=f"data.{row_index}.{axis_key}", maximum=30, error_type=InvalidChartError)
            periods.append(period)
            for key in keys:
                require_decimal_string(row.get(key), field=f"data.{row_index}.{key}", error_type=InvalidChartError)
        if len(periods) != len(set(periods)):
            raise InvalidChartError(details={"field": "data"})
        parsed_periods = []
        month_lookup = {name: index for index, name in enumerate(SPANISH_MONTH_NAMES, start=1)}
        for period in periods:
            match = re.fullmatch(r"([A-Za-záéíóúÁÉÍÓÚñÑ]+) de (\d{4})", period)
            if match is None or match.group(1) not in month_lookup:
                parsed_periods = []
                break
            parsed_periods.append((int(match.group(2)), month_lookup[match.group(1)]))
        if parsed_periods and parsed_periods != sorted(parsed_periods):
            raise InvalidChartError(details={"field": "data.period"})


class RecommendationBlock(VisualBlock):
    block_type = BlockType.RECOMMENDATION.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "level", "headline", "explanation", "reasons", "confidence"})
        reject_unknown_fields(payload, allowed={"type", "id", "level", "headline", "explanation", "reasons", "confidence"})
        require_id(payload["id"])
        require_enum(payload["level"], RecommendationLevel, field="level")
        require_string(payload["headline"], field="headline", maximum=90)
        require_string(payload["explanation"], field="explanation", maximum=180)
        reasons = require_list(payload["reasons"], field="reasons")
        if not 1 <= len(reasons) <= 5:
            raise InvalidVisualBlockError(details={"field": "reasons"})
        for index, reason in enumerate(reasons):
            require_mapping(reason, field=f"reasons.{index}")
            require_fields(reason, required={"code", "text"})
            reject_unknown_fields(reason, allowed={"code", "text"})
            require_id(reason["code"], field=f"reasons.{index}.code")
            require_string(reason["text"], field=f"reasons.{index}.text", maximum=140)
        if payload["confidence"] not in {
            Confidence.LOW.value,
            Confidence.MEDIUM.value,
            Confidence.HIGH.value,
        }:
            raise InvalidVisualBlockError(details={"field": "confidence"})


class QuestionBlock(VisualBlock):
    block_type = BlockType.QUESTION.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "question", "reason", "input"})
        reject_unknown_fields(payload, allowed={"type", "id", "question", "reason", "input"})
        require_id(payload["id"])
        require_string(payload["question"], field="question", maximum=140)
        require_string(payload["reason"], field="reason", maximum=180)
        input_data = require_mapping(payload["input"], field="input")
        require_fields(input_data, required={"type", "key", "required"})
        reject_unknown_fields(input_data, allowed={"type", "key", "required", "currency", "options"})
        require_enum(input_data["type"], QuestionInputType, field="input.type")
        require_id(input_data["key"], field="input.key")
        if not isinstance(input_data["required"], bool):
            raise InvalidVisualBlockError(details={"field": "input.required"})
        if input_data["type"] == QuestionInputType.CURRENCY.value:
            require_string(input_data.get("currency"), field="input.currency", maximum=3)
        if input_data["type"] in {QuestionInputType.SINGLE_CHOICE.value, QuestionInputType.MULTIPLE_CHOICE.value}:
            options = require_list(input_data.get("options"), field="input.options")
            if not 1 <= len(options) <= 10:
                raise InvalidVisualBlockError(details={"field": "input.options"})
            for index, option in enumerate(options):
                require_string(option, field=f"input.options.{index}", maximum=80)
            if len(set(options)) != len(options):
                raise InvalidVisualBlockError(details={"field": "input.options"})


class ActionGroupBlock(VisualBlock):
    block_type = BlockType.ACTION_GROUP.value

    @classmethod
    def validate(cls, payload):
        _validate_type(payload, cls.block_type)
        require_fields(payload, required={"type", "id", "layout", "actions"})
        reject_unknown_fields(payload, allowed={"type", "id", "layout", "actions"})
        require_id(payload["id"])
        require_enum(payload["layout"], ActionLayout, field="layout")
        actions = require_list(payload["actions"], field="actions")
        if not 1 <= len(actions) <= MAX_ACTIONS:
            raise InvalidVisualBlockError(details={"field": "actions"})
        from core.assistant.visual_contract.actions import validate_actions

        validate_actions(actions)
