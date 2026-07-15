# Endpoint experimental del asistente

> Fase 3: el endpoint intenta primero el motor determinista. Las consultas conocidas devuelven el contrato visual `1.0` con `source=deterministic` y no invocan provider. El mock queda como fallback compatible.

## Contrato

`POST /api/assistant/messages/` está registrado como `AssistantMessageView` y usa la autenticación global real: sesión Django/DRF, `IsAuthenticated` y CSRF en solicitudes de sesión no exentas.

Entrada por mensaje:

```json
{"message": "budget:2026-09", "conversation_id": null}
```

Entrada de detalle:

```json
{"intent": "monthly_summary_detail", "arguments": {"year": 2026, "month": 9}}
```

Se acepta `message` o `intent+arguments`, nunca ambos. `message` no puede estar vacío ni exceder `ASSISTANT_MAX_MESSAGE_LENGTH` (200 por defecto). `conversation_id` se valida pero no se almacena ni se usa aún. `user_id`, `family_id`, bloques y campos adicionales son rechazados. El objeto arguments solo admite `year` y `month`.

Las consultas naturales reconocidas devuelven el sobre documentado en `17-visual-contract-v1.md`. El ejemplo legacy siguiente solo aplica al fallback mock.

Respuesta exitosa resumida:

```json
{
  "message": "Septiembre de 2026: 2450.00 EUR planificados, 1760.00 pagados y 690.00 pendientes.",
  "period": {"year": 2026, "month": 9, "label": "Septiembre de 2026"},
  "tool_calls": [{"name": "get_monthly_budget", "status": "success"}],
  "data": {},
  "provider": "mock",
  "request_id": "UUID"
}
```

`data` contiene el DTO completo de la tool. No hay stack traces ni contratos CRUD crudos.

## Configuración segura

```text
ASSISTANT_ENABLED=False
ASSISTANT_PROVIDER=mock
ASSISTANT_MAX_MESSAGE_LENGTH=200
DEFAULT_CURRENCY=EUR
```

Desactivado devuelve HTTP 503 con `assistant_disabled`. Un proveedor distinto de `mock` devuelve `provider_unavailable`; no hay fallback externo.

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

La view obtiene `Profile.family` desde `request.user`; el mensaje no selecciona identidad. El servicio registra `request_id`, referencias HMAC truncadas de actor/familia, provider, tool, estado, duración y código de error. No registra mensaje, DTO financiero, email, cookie, token ni autorización. No se creó tabla de conversaciones.

Las necesidades no cubiertas se clasifican en memoria/log como `unsupported_intent`, `missing_endpoint`, `insufficient_data`, `invalid_arguments`, `permission_denied`, `technical_error` u `out_of_domain`; tampoco se guarda la pregunta completa.

## Estado

Implementado y probado como superficie experimental desactivada por defecto. Puede resolver preguntas frecuentes y acciones Ver más sin tokens. El fallback sigue siendo mock; no debe presentarse todavía como integración con IA real.
