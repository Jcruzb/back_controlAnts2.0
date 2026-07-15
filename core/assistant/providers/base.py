from dataclasses import dataclass
from typing import Any, Dict, Protocol, Sequence


@dataclass(frozen=True)
class ProviderDecision:
    tool_name: str
    arguments: Dict[str, Any]


class AssistantProvider(Protocol):
    name: str

    def respond(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        available_tools,
        context: Dict[str, Any],
    ) -> ProviderDecision:
        ...

