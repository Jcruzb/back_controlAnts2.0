from enum import Enum


SCHEMA_VERSION = "1.0"
BLOCK_VERSION = "1.0"

MAX_BLOCKS = 10
MAX_VISIBLE_ALERTS = 2
MAX_ACTIONS = 3
MAX_METRICS = 4
MIN_METRICS = 2
MAX_TABLE_COLUMNS = 5
MAX_TABLE_ROWS = 10
MAX_BAR_CATEGORIES = 10
MAX_BAR_SERIES = 2
MAX_LINE_SERIES = 3


class StringEnum(str, Enum):
    @classmethod
    def values(cls):
        return {item.value for item in cls}


class ResponseSource(StringEnum):
    DETERMINISTIC = "deterministic"
    AI = "ai"
    HYBRID = "hybrid"


class BlockType(StringEnum):
    SUMMARY_CARD = "summary_card"
    METRIC_GRID = "metric_grid"
    ALERT = "alert"
    SIMPLE_TABLE = "simple_table"
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    RECOMMENDATION = "recommendation"
    QUESTION = "question"
    ACTION_GROUP = "action_group"


class Status(StringEnum):
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    ATTENTION = "attention"
    NEGATIVE = "negative"
    CRITICAL = "critical"


class AlertSeverity(StringEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TrendDirection(StringEnum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class TrendMeaning(StringEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class TableFormat(StringEnum):
    TEXT = "text"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    DATE = "date"
    INTEGER = "integer"
    STATUS = "status"


class Alignment(StringEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class DataKind(StringEnum):
    ACTUAL = "actual"
    PLANNED = "planned"
    PROJECTED = "projected"
    SIMULATED = "simulated"


class RecommendationLevel(StringEnum):
    RECOMMENDED = "recommended"
    ACCEPTABLE_WITH_CONDITIONS = "acceptable_with_conditions"
    NOT_RECOMMENDED = "not_recommended"
    NOT_AFFORDABLE = "not_affordable"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class Confidence(StringEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    NONE = "none"


class QuestionInputType(StringEnum):
    TEXT = "text"
    CURRENCY = "currency"
    INTEGER = "integer"
    DATE = "date"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    BOOLEAN = "boolean"


class ActionType(StringEnum):
    FETCH_DETAIL = "fetch_detail"
    NAVIGATE = "navigate"
    SEND_INTENT = "send_intent"
    SUBMIT_ANSWER = "submit_answer"
    EXPAND = "expand"
    COLLAPSE = "collapse"


class ActionStyle(StringEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"
    GHOST = "ghost"


class ActionLayout(StringEnum):
    PRIMARY_SECONDARY = "primary_secondary"
    INLINE = "inline"
    STACKED = "stacked"
