# Registro de necesidades no cubiertas

> La fase 2 implementa únicamente el clasificador y logging minimizado sin tabla. La persistencia, retención agregada y panel descritos aquí permanecen como propuesta futura.

## Objetivo y límite

Registrar por qué una consulta no se resolvió para orientar el backlog. El registro **no** autoriza al modelo a crear endpoints, modificar código ni ejecutar migraciones.

## Evento propuesto

```json
{
  "event_id": "uuid",
  "conversation_turn_id": "opaque-id",
  "normalized_intent": "forecast_monthly_spending",
  "status": "unsupported",
  "reason_code": "missing_capability",
  "reason_detail": "No existe servicio ni endpoint de forecast",
  "available_tools_checked": ["get_monthly_budget", "list_month_expenses"],
  "tool_failures": [],
  "missing_capability": "monthly_spending_forecast",
  "suggested_backend_need": "Forecast service based on validated history",
  "anonymized_context": {
    "period_granularity": "month",
    "month": 12,
    "has_explicit_year": false
  },
  "impact_hint": "planning",
  "provider": "provider-key-without-model-prompt",
  "created_at": "ISO-8601",
  "retention_class": "product_analytics_90d"
}
```

`user_question` literal no debe almacenarse por defecto. Si producto necesita muestras para diagnóstico, guardar una versión redactada y muestreada con consentimiento/configuración, nunca el texto completo automáticamente.

## Taxonomía de resultados

| `reason_code` | Significado | Ejemplo | Acción |
|---|---|---|---|
| `understanding_failure` | Hay tool, pero no se pudo normalizar intent/periodo/entidad | “lo de antes” sin referente | mejorar resolver conversacional |
| `missing_capability` | No existe tool/service/endpoint | forecast | backlog de capacidad |
| `insufficient_data` | Endpoint existe, respuesta carece de datos | plan sin versión | calidad/contrato/datos |
| `technical_error` | timeout, 5xx, parseo, dependencia | backend no disponible | fiabilidad/alerta |
| `permission_denied` | 401/403 o rol insuficiente | miembro crea categoría | UX/permisos; no reintentar |
| `out_of_domain` | No pertenece a ControlAnts | clima | respuesta segura, no backlog financiero |
| `ambiguous_request` | Varias interpretaciones materiales | “lo que queda” | aclaración o mejor contexto |
| `validation_error` | Parámetros fuera de rango/entidad no válida | mes 13 | corregir entrada |
| `confirmation_missing` | Escritura preparada pero no confirmada | delete | no ejecutar; no es fallo técnico |

## Minimización y datos prohibidos

### Almacenar

- intent normalizado, razón codificada, tools comprobadas;
- dimensiones no identificables: mes numérico, granularidad, tipo de entidad;
- latencia, código HTTP, clase de error redactada;
- rol general (`admin|member`) solo si es necesario para analizar permisos;
- hash rotatorio de familia/usuario para contar recurrencia sin identidad directa.

### No almacenar

- nombres, emails, usernames, contraseñas, cookies, CSRF o cabeceras;
- importes exactos, descripciones de movimientos o payloads completos;
- prompts del sistema, respuestas completas del proveedor o stack traces con datos;
- IDs de base de datos en claro;
- conversación completa;
- datos de otra familia o contenido devuelto por tools que no sea necesario para clasificar.

## Anonimización

1. Normalizar el intent con vocabulario cerrado.
2. Extraer solo slots permitidos y convertir importes en bandas opcionales, no valores.
3. Reemplazar entidades por tipos (`category_reference`, `person_reference`).
4. Usar HMAC rotatorio, con secreto fuera de DB, si se necesita deduplicar tenant/usuario.
5. Ejecutar redacción antes de persistir y rechazar el evento si el redactor falla.

## Agrupación de preguntas equivalentes

Clave sugerida:

```text
normalized_intent + reason_code + missing_capability + slot_signature + toolset_version
```

Ejemplos “¿qué gastaré en diciembre?” y “previsión del próximo mes” agrupan en `forecast_monthly_spending`, pero conservan dimensiones `explicit_month`/`relative_month` para analizar comprensión de fechas.

## Priorización

Puntuación semanal reproducible:

```text
score = unique_families_30d * frequency_weight
      + affected_turns_30d * 0.25
      + impact_weight
      + blocked_write_weight
      - workaround_weight
```

- Impacto básico/errores financieros: +10.
- Bloquea una lectura frecuente: +6.
- Bloquea escritura confirmada: +5.
- Existe alternativa segura actual: −4.
- Out-of-domain: no entra al backlog de producto.

No priorizar solo por volumen: mostrar familias únicas, tasa de repetición, severidad, conversión tras aclaración y porcentaje de errores técnicos.

## Vista para desarrollo

Dashboard interno con:

- ranking por capability/reason y tendencia semanal;
- filtros por versión de tools, rol y estado;
- ejemplos redactados muestreados;
- desglose `unsupported` frente a `technical_error`;
- enlace a issue/ADR y estado `new|triaged|planned|released|wont_fix`;
- comparación antes/después de publicar una tool.

Acceso restringido por rol, exportaciones auditadas y sin drill-down a identidad real.

## Retención y privacidad

- Eventos agregables: 90 días; métricas agregadas anónimas: 12 meses.
- Errores técnicos con detalle redactado: 30 días.
- Muestras textuales consentidas: 30 días máximo.
- Borrado automático, documentado y verificable.
- Base jurídica/consentimiento según despliegue; informar en privacidad y permitir exclusión de analítica no esencial.
- Cifrado en tránsito/reposo, control de acceso, auditoría de consultas y procedimiento de borrado.
