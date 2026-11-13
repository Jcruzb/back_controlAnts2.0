# IA solo bajo demanda

`POST /api/assistant/messages/` conserva las consultas deterministas y los intents de lectura.
Los mensajes no reconocidos devuelven HTTP 409 con `error.code = ai_consent_required`;
no se construye ni llama a ningún proveedor, incluido el mock.

El frontend ofrece reformular o pulsar **Consultar con IA**. Solo ese segundo envío
incluye `allow_ai: true`, un booleano JSON estricto. No se acepta en peticiones de
`intent`. La autorización vale únicamente para ese mensaje y no se guarda.

```json
{"message":"Dime cuál es la liquidez disponible","context":{"year":2026,"month":9},"allow_ai":true}
```

Si la consulta puede resolverse de forma determinista, no utiliza proveedor aunque
`allow_ai` sea true. Las respuestas visuales siguen el contrato 1.0. El proveedor
solo recibe pregunta y periodo; no recibe movimientos ni identificadores de familia.
La funcionalidad continúa siendo de solo lectura, protegida por sesión/CSRF y por
`ASSISTANT_ENABLED`. OpenAI necesita sus variables existentes configuradas.

Cambio de compatibilidad: clientes anteriores ya no escalan automáticamente; deben
manejar el código 409 y solicitar consentimiento explícito antes del reintento.
El frontend mantiene hasta 10 consultas en memoria y permite revisar sus respuestas.
Se borran al cambiar usuario, familia, periodo o salir de la página. No se envía el
historial al proveedor ni se promete memoria conversacional entre preguntas.

Validación: `python manage.py test core.test_assistant core.test_assistant_visual`.
Los tests simulan el proveedor, no consumen IA ni necesitan credenciales externas.
