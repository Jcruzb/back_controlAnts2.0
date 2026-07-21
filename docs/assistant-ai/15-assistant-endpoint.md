# Endpoint del asistente financiero

El endpoint intenta primero el motor determinista. Las consultas conocidas devuelven el contrato visual `1.0` con `source=deterministic` y no consumen tokens. Las preguntas libres pueden pasar por OpenAI para seleccionar una consulta permitida; los datos y la presentación final siguen siendo deterministas.

## Contrato

`POST /api/assistant/messages/` está registrado como `AssistantMessageView` y usa la autenticación global real: sesión Django/DRF, `IsAuthenticated` y CSRF en solicitudes de sesión no exentas.

Entrada por mensaje:

```json
{"message": "¿Cómo va nuestra liquidez?", "context": {"year": 2026, "month": 9}}
```

Entrada de detalle:

```json
{"intent": "monthly_summary_detail", "arguments": {"year": 2026, "month": 9}}
```

Se acepta `message` o `intent+arguments`, nunca ambos. `message` no puede estar vacío ni exceder `ASSISTANT_MAX_MESSAGE_LENGTH` (200 por defecto). El `context` opcional solo admite `year` y `month` y fija el periodo seleccionado en el frontend para expresiones como «este mes». `conversation_id` se valida pero no se almacena ni se usa aún. `user_id`, `family_id`, bloques y campos adicionales son rechazados. El objeto arguments solo admite `year` y `month`.

Todas las respuestas exitosas devuelven el sobre documentado en `17-visual-contract-v1.md`. Una consulta enrutada por IA se identifica con `source=hybrid` y añade metadatos no sensibles:

```json
{
  "schema_version": "1.0",
  "source": "hybrid",
  "intent": "monthly_cash_balance",
  "summary": "El balance de caja del mes es positivo",
  "period": {"year": 2026, "month": 9, "label": "Septiembre de 2026", "timezone": "Europe/Madrid"},
  "blocks": [],
  "meta": {
    "provider": "openai",
    "model": "modelo-configurado",
    "tool_call": {"name": "get_monthly_cash_summary", "status": "success"}
  }
}
```

## Configuración segura

```text
ASSISTANT_ENABLED=False
ASSISTANT_PROVIDER=mock
ASSISTANT_MAX_MESSAGE_LENGTH=200
ASSISTANT_PROVIDER_TIMEOUT_SECONDS=20
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_CURRENCY=EUR
```

Para activar OpenAI: `ASSISTANT_ENABLED=True`, `ASSISTANT_PROVIDER=openai` y valores reales en `OPENAI_API_KEY` y `OPENAI_MODEL`. Si falta la credencial o el modelo devuelve HTTP 503 con `provider_unavailable`. Nunca se usa una variable `VITE_*` para secretos.

## Errores estables

- `invalid_arguments` (400)
- `unsupported_tool` (400)
- `unsupported_request` (400)
- `permission_denied` (403)
- `resource_not_found` (404)
- `assistant_disabled` (503)
- `provider_unavailable` (503)
- `tool_execution_failed` (500)

La forma es `{"error":{"code","message","details?"}}` y los detalles solo señalan campos seguros.

## Tenant, privacidad y trazas

La view obtiene `Profile.family` desde `request.user`; el mensaje no selecciona identidad. OpenAI recibe solo la pregunta y el periodo seleccionado para clasificar una de seis intenciones de lectura. No recibe ids de actor/familia ni DTOs financieros. El servicio registra `request_id`, referencias HMAC truncadas de actor/familia, provider, tool, estado, duración y código de error. No registra mensaje, DTO financiero, email, cookie, token ni autorización. No se creó tabla de conversaciones.

Las necesidades no cubiertas se clasifican en memoria/log como `unsupported_intent`, `missing_endpoint`, `insufficient_data`, `invalid_arguments`, `permission_denied`, `technical_error` u `out_of_domain`; tampoco se guarda la pregunta completa.

## Estado

Implementado y probado como superficie de solo lectura desactivada por defecto. Puede resolver preguntas frecuentes y acciones Ver más sin tokens. Con `ASSISTANT_PROVIDER=openai`, las preguntas libres se enrutan mediante Responses API y luego se contestan con datos reales de ControlAnts.
