import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from core.assistant.errors import ProviderUnavailableError, UnsupportedRequestError
from core.assistant.providers.base import ProviderDecision


ROUTE_TOOL_NAME = "select_financial_intent"
INTENT_TO_TOOL = {
    "monthly_summary": "get_monthly_budget",
    "monthly_spending": "list_monthly_expenses",
    "monthly_cash_balance": "get_monthly_cash_summary",
    "pending_payments": "get_recurring_payment_status",
    "category_spending": "get_category_spending",
    "payer_spending": "get_payer_spending",
}

ROUTER_INSTRUCTIONS = """
Eres el enrutador de lectura del copiloto financiero ControlAnts.
Clasifica la pregunta en una sola intención permitida y llama a la función indicada.
Usa el periodo seleccionado salvo que la persona mencione explícitamente otro mes o año.
No calcules importes, no respondas con texto y no inventes datos ni identificadores.
Elige unsupported si la pregunta no puede responderse con una de las intenciones permitidas.
""".strip()


class OpenAIAssistantProvider:
    name = "openai"

    def __init__(self, *, api_key=None, model=None, base_url=None, timeout=None, opener=None):
        self.api_key = (api_key if api_key is not None else settings.OPENAI_API_KEY).strip()
        self.model = (model if model is not None else settings.OPENAI_MODEL).strip()
        self.base_url = (
            base_url if base_url is not None else settings.OPENAI_BASE_URL
        ).rstrip("/")
        self.timeout = timeout or settings.ASSISTANT_PROVIDER_TIMEOUT_SECONDS
        self.opener = opener or urlopen

        if not self.api_key or not self.model:
            raise ProviderUnavailableError(
                "Configura OPENAI_API_KEY y OPENAI_MODEL para activar el proveedor OpenAI."
            )

    def respond(self, *, messages, available_tools, context):
        if not messages:
            raise UnsupportedRequestError()

        message = str(messages[-1].get("content", "")).strip()
        if not message:
            raise UnsupportedRequestError()

        default_period = context.get("default_period") or {}
        input_text = (
            f"Periodo seleccionado: {default_period.get('year')}-"
            f"{int(default_period.get('month', 1)):02d}\n"
            f"Pregunta: {message}"
        )
        payload = {
            "model": self.model,
            "instructions": ROUTER_INSTRUCTIONS,
            "input": input_text,
            "tools": [self._route_tool_schema()],
            "tool_choice": {"type": "function", "name": ROUTE_TOOL_NAME},
            "parallel_tool_calls": False,
        }

        response = self._request(payload)
        call = next(
            (
                item
                for item in response.get("output", [])
                if item.get("type") == "function_call" and item.get("name") == ROUTE_TOOL_NAME
            ),
            None,
        )
        if call is None:
            raise ProviderUnavailableError(
                "El proveedor no devolvió una intención financiera válida."
            )

        arguments = call.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise ProviderUnavailableError(
                    "El proveedor devolvió argumentos no válidos."
                ) from error
        if not isinstance(arguments, dict):
            raise ProviderUnavailableError("El proveedor devolvió argumentos no válidos.")

        intent = arguments.get("intent")
        if intent == "unsupported":
            raise UnsupportedRequestError(
                "Nilo solo puede responder preguntas sobre los datos financieros disponibles."
            )

        tool_name = INTENT_TO_TOOL.get(intent)
        available_names = {item["name"] for item in available_tools}
        if tool_name is None or tool_name not in available_names:
            raise ProviderUnavailableError(
                "El proveedor seleccionó una consulta no disponible."
            )

        return ProviderDecision(
            tool_name=tool_name,
            arguments={
                "year": arguments.get("year"),
                "month": arguments.get("month"),
            },
        )

    def _request(self, payload):
        request = Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code in {401, 403}:
                message = "La credencial de OpenAI no es válida o no tiene acceso al modelo."
            elif error.code == 429:
                message = "OpenAI ha limitado temporalmente las solicitudes."
            else:
                message = "OpenAI no ha podido procesar la solicitud."
            raise ProviderUnavailableError(message) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ProviderUnavailableError(
                "No se pudo conectar con OpenAI o interpretar su respuesta."
            ) from error

    @staticmethod
    def _route_tool_schema():
        return {
            "type": "function",
            "name": ROUTE_TOOL_NAME,
            "description": "Selecciona una consulta financiera de solo lectura y su periodo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": [*INTENT_TO_TOOL.keys(), "unsupported"],
                    },
                    "year": {"type": "integer", "minimum": 1, "maximum": 9999},
                    "month": {"type": "integer", "minimum": 1, "maximum": 12},
                },
                "required": ["intent", "year", "month"],
                "additionalProperties": False,
            },
            "strict": True,
        }
