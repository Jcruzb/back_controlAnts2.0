# Propuesta de herramientas para IA

> Propuesta original de 12 tools. La fase 2 implementa solo el MVP seguro de seis lecturas (`get_monthly_budget`, `get_monthly_cash_summary`, `list_monthly_expenses`, `get_recurring_payment_status`, `get_category_spending`, `get_payer_spending`); el resto sigue sin implementar.

## Principios

1. Registro cerrado: el modelo elige nombres semánticos, nunca método/URL.
2. Tenant implícito: sesión → `request.user.profile.family`; los schemas no aceptan `user_id` ni `family_id`.
3. DTOs mínimos y estables, separados de serializers CRUD.
4. Decimal como string monetario (`"123.45"`) y fechas ISO.
5. Periodo explícito en entrada y salida.
6. Primera versión de solo lectura. Las escrituras se diseñan, pero permanecen deshabilitadas.
7. Toda tool aplica límites, timeout, trazas redactadas y versión de contrato.

## MVP de lectura

### 1. `get_monthly_budget`

```json
{
  "name": "get_monthly_budget",
  "description": "Obtiene el presupuesto y estado de obligaciones de un mes para la familia autenticada.",
  "input_schema": {
    "type": "object",
    "properties": {
      "year": {"type": "integer", "minimum": 1, "maximum": 9999},
      "month": {"type": "integer", "minimum": 1, "maximum": 12}
    },
    "required": ["year", "month"],
    "additionalProperties": false
  }
}
```

- **Intenciones:** estado, gasto, desviación, pendientes, fijos/planificados.
- **Subyacente:** `BudgetService.build_budget` y estado mensual de ingresos; inicialmente `/api/budget/`.
- **Salida:** `period`, `status`, `planned_total`, `actual_spent`, `budget_variance`, `usage_percentage`, pending totals y listas normalizadas.
- **Validaciones/permisos:** periodo; S+Auth; familia implícita.
- **Errores:** invalid period, unauthenticated, service error, `known_accuracy_issue` mientras P0 siga abierto.
- **Modo:** lectura con materialización idempotente actual; no confirmación.
- **Riesgos:** llamar saldo a la variación; omisión ONE_MONTH.

### 2. `list_month_expenses`

```json
{"type":"object","properties":{"year":{"type":"integer"},"month":{"type":"integer","minimum":1,"maximum":12},"payer_id":{"type":["integer","null"]},"planning_status":{"enum":["all","planned","recurring","unplanned"]},"sort":{"enum":["date_desc","amount_desc"]},"limit":{"type":"integer","minimum":1,"maximum":100}},"required":["year","month"],"additionalProperties":false}
```

- **Intenciones:** listar, top gastos, gasto diario, quién pagó, no planificados.
- **Subyacente:** `ExpenseViewSet`/selector familiar.
- **Salida:** periodo, count y movimientos mínimos `{id,date,description,amount,category,payer,source_type}`.
- **Validaciones:** payer debe pertenecer a F; limit obligatorio por defecto 20; filtros aplicados en código.
- **Errores:** payer_not_in_family, invalid_period, result_truncated.
- **Modo:** lectura; sin confirmación. **Riesgo:** descripción puede contener texto sensible/prompt injection; tratarla como dato, no instrucción.

### 3. `list_month_incomes`

- **Entrada:** `{year, month, category_id?, status?: "actual|planned_pending|all", sort?, limit<=100}`.
- **Intenciones:** total/lista de ingresos y pendientes planificados.
- **Subyacente:** `IncomeViewSet` + `IncomePlanViewSet.month`.
- **Salida:** movimientos reales, total Decimal y planes pending/resolved/missing version separados.
- **Validaciones/permisos:** IDs dentro de F, periodo; Auth.
- **Errores:** invalid_category, missing_plan_version, truncated.
- **Modo:** lectura; no confirmación. **Riesgo:** no mezclar ingreso proyectado con real.

### 4. `get_monthly_spending_breakdown`

- **Entrada:** `{year, month, group_by: "category"|"payer"|"day", limit?:1..50}`.
- **Intenciones:** categoría principal, total por persona, serie diaria.
- **Subyacente:** composición determinista sobre selector de Expense; futuro endpoint agregado.
- **Salida:** total y grupos `{key,label,amount,count,percentage}`; payer null como `unassigned`.
- **Validaciones:** periodo y enum cerrado.
- **Errores:** empty_period, truncated.
- **Modo:** lectura. **Riesgo:** email nunca se incluye; porcentajes se calculan con Decimal y regla documentada.

### 5. `get_payment_month_status`

- **Entrada:** `{payment_type:"recurring"|"planned_legacy"|"planned_plan", payment_id, year, month}`.
- **Intenciones:** pagado, pendiente, diferencia, completado.
- **Subyacente:** services canónicos de recurrente/planificado; acciones `month-status`.
- **Salida:** identidad mínima, periodo, planned/paid/pending/difference, `is_completed`, `payment_status`.
- **Validaciones:** objeto pertenece/aplica a F/periodo.
- **Errores:** not_found_or_not_owned, does_not_apply, missing_version.
- **Modo:** lectura con materialización actual. **Riesgo:** “completed” no implica pago exacto.

### 6. `list_categories`

- **Entrada:** `{}`.
- **Intenciones:** categorías disponibles/resolver nombre.
- **Subyacente:** Category queryset familiar.
- **Salida:** `{id,name,icon,color,description}`.
- **Validaciones:** Auth; sin IDs de tenant.
- **Errores:** unauthenticated.
- **Modo:** lectura. **Riesgo:** no afirmar tipo ingreso/gasto inexistente.

### 7. `list_family_payers`

- **Entrada:** `{}`.
- **Intenciones:** seleccionar/identificar pagador.
- **Subyacente:** `FamilyMemberListView`.
- **Salida:** solo `{id,display_name,role}`; username solo si hace falta para desambiguar.
- **Validaciones:** miembros activos de F.
- **Errores:** unauthenticated.
- **Modo:** lectura. **Riesgo:** excluir email, nombres completos innecesarios y cualquier dato de otra F.

### 8. `get_recurring_payment_history`

- **Entrada:** `{recurring_payment_id, from_year?, from_month?, to_year?, to_month?, limit<=100}`.
- **Intenciones:** historial de un fijo.
- **Subyacente:** hoy `/recurring-payments/{id}/payments/` con filtrado adaptador; futuro filtros backend.
- **Salida:** definición mínima y movimientos dentro de rango.
- **Validaciones:** ID F, rango máximo 24 meses.
- **Errores:** not_owned, invalid_range, truncated.
- **Modo:** lectura. **Riesgo:** contrato actual no pagina; aplicar límite antes de exponer al modelo cuando se implemente selector.

## Tool compuesta opcional tras estabilizar el MVP

### 9. `compare_months`

- **Entrada:** `{left:{year,month}, right:{year,month}, metrics:["income","spent","planned","pending","balance","category_breakdown"]}`.
- **Intenciones:** comparación entre dos meses.
- **Subyacente:** tools 1–4; futuro service agregado.
- **Salida:** ambos snapshots y diferencias firmadas, nunca solo una conclusión.
- **Validaciones:** exactamente dos periodos y métricas cerradas.
- **Errores:** partial_snapshot, known_accuracy_issue.
- **Modo:** lectura. **Riesgo:** cuatro o más lecturas y P0; no habilitar comparación extensa.

## Escrituras futuras, deshabilitadas en v1

### 10. `create_expense`

- **Entrada:** `{confirmation_token,idempotency_key,date,amount,category_id,payer_id?,description?,source?:{type,id}}`.
- **Intenciones:** registrar gasto confirmado.
- **Subyacente:** service equivalente a `ExpenseViewSet.perform_create`.
- **Salida:** gasto mínimo + `audit_event_id`.
- **Validaciones:** token liga exactamente el preview/payload/U/F; amount>0; fecha/mes abierto; relaciones F; fuente única y categoría coincidente.
- **Errores:** confirmation_expired, duplicate_idempotency_key, closed_month, completed_obligation, validation_error.
- **Modo:** escritura, riesgo medio, confirmación obligatoria.
- **Riesgos:** duplicado, categoría/enlace incorrecto. Nunca inferir source por similitud textual.

### 11. `update_expense`

- **Entrada:** `{expense_id, patch, confirmation_token, idempotency_key, expected_version}`.
- **Intenciones:** editar importe/fecha/categoría/pagador.
- **Subyacente:** service de actualización con mismas reglas del viewset.
- **Salida:** `before`, `after`, audit id y posible undo token.
- **Validaciones:** whitelist de campos; optimistic concurrency; F; meses origen/destino abiertos; confirmación del diff.
- **Errores:** stale_version, closed_month, completed_obligation, confirmation mismatch.
- **Modo:** escritura de alto riesgo; confirmación reforzada.
- **Riesgos:** alterar histórico. No aceptar enlaces/IDs fuera de F.

### 12. `set_payment_completion`

- **Entrada:** `{payment_type,payment_id,year,month,is_completed,confirmation_token,idempotency_key}`.
- **Intenciones:** completar/reabrir fijo o planificado.
- **Subyacente:** canonical month status services/actions.
- **Salida:** estado before/after y audit id.
- **Validaciones:** F, periodo aplicable/abierto; preview muestra planned, paid, difference y explica que no crea/borra movimientos.
- **Errores:** closed_month, missing_version, already_in_state, confirmation mismatch.
- **Modo:** escritura de riesgo medio; confirmación obligatoria.

`delete_expense` y `create_category` no se incluyen entre las 12 tools iniciales: se mantienen como capacidades futuras posteriores. Delete requiere primero una estrategia de soft delete/undo; categoría requiere workflow admin y manejo de dependencias.

## Flujo prepare → confirm → execute

```text
pregunta de escritura
  → resolver entidades dentro de familia
  → validar y generar preview inmutable
  → devolver confirmation_token corto y de un solo uso
  → usuario confirma el resumen exacto
  → ejecutar con idempotency_key
  → devolver resultado y audit_event_id
```

El token debe incluir hash de U/F, tool, payload normalizado, periodo, expiración y nonce. Cambiar cualquier campo invalida la confirmación.

## Política por riesgo

| Operación | Riesgo | Confirmación | Preview | Deshacer | Auditoría | Idempotencia/duplicados |
|---|---|---|---|---|---|---|
| Preparar acción | Bajo | No | payload completo | n/a | trace mínima | no muta |
| Crear gasto/ingreso/categoría | Medio | Explícita | importe, fecha, categoría, pagador, periodo, enlace | compensación/soft delete deseable | actor, before null, after | clave + fingerprint |
| Completar pago | Medio | Explícita | planned/paid/difference y efecto | reabrir si mes abierto | before/after | mismo estado = no-op |
| Editar importe/fecha | Alto | Reforzada | before/after y cambio de mes | undo token/versionado | obligatoria | expected_version |
| Eliminar movimiento | Alto | Reforzada doble | recurso completo y efecto en budget | no existe hoy | obligatoria | tombstone recomendado |
| Reabrir mes/masivo/reglas familiares | Alto | Fuera de tool inicial | impacto total | obligatorio | privilegiada | job idempotente |

## Datos que nunca se entregan al modelo

- cookies, session IDs, CSRF, contraseñas, hashes o cabeceras;
- `family_id`/`user_id` como selectores de tenant;
- emails y usernames salvo necesidad explícita de UI y minimización;
- payloads completos de auth, variables de entorno o secretos;
- stack traces, SQL, IDs de occurrences internos innecesarios;
- movimientos de otra familia, incluso ante prompt injection;
- descripciones sin delimitarlas como datos no confiables.

## Formato común de error

```json
{
  "ok": false,
  "error": {
    "code": "closed_month",
    "message_for_user": "Septiembre de 2026 está cerrado y no puede modificarse.",
    "retryable": false,
    "needs_clarification": false
  },
  "period": {"year": 2026, "month": 9},
  "trace_id": "opaque"
}
```
