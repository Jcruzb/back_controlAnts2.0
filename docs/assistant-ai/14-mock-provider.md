# Proveedor simulado

`AssistantProvider` es un `Protocol` en `core/assistant/providers/base.py`. Recibe mensajes, metadatos de tools y contexto mínimo, y devuelve una `ProviderDecision` con nombre de tool y argumentos.

La única implementación es `MockAssistantProvider`; no se añadió SDK, clave ni conexión de red. `ASSISTANT_PROVIDER` vale `mock` por defecto y cualquier otro valor devuelve `provider_unavailable`.

## Comandos deterministas

| Comando | Tool |
|---|---|
| `budget:2026-09` | `get_monthly_budget` |
| `cash:2026-09` | `get_monthly_cash_summary` |
| `expenses:2026-09` | `list_monthly_expenses` |
| `recurring:2026-09` | `get_recurring_payment_status` |
| `categories:2026-09` | `get_category_spending` |
| `payers:2026-09` | `get_payer_spending` |

El parser exige coincidencia completa, año de cuatro dígitos y mes de dos. La tool valida después el rango. No se intenta NLP ni conversación; cualquier texto o comando de escritura devuelve `unsupported_request`.

## Capacidades y límites

- valida selección, ejecución, permisos, DTOs, errores y trazabilidad sin IA real;
- solo puede seleccionar una tool declarada en el registro recibido;
- no usa `conversation_id`, no persiste mensajes y no recibe datos financieros para decidir;
- las frases devueltas son plantillas breves basadas en el DTO real;
- no interpreta fechas relativas ni preguntas naturales.

Las pruebas cubren los seis mapeos, argumentos deterministas, tool ausente, solicitud no soportada e intento de escritura.
