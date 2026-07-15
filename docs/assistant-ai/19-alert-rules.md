# Reglas de alertas objetivas

Umbral configurable: `ASSISTANT_BUDGET_NEAR_LIMIT_PERCENT=90.00`. La evaluación usa `Decimal` y DTOs canónicos; no inspecciona texto libre ni recomendaciones.

| Código | Condición exacta | Severidad | Prioridad | Datos usados | Acción | Pruebas |
|---|---|---|---:|---|---|---|
| `expenses_over_income` | `actual_income > 0` y `total_spent > actual_income` | critical | 10 | ingreso, gasto, cash balance | Ver gastos | exceso y orden |
| `budget_exceeded` | `total_planned > 0` y `percentage_used >= 100` | critical | 20 | plan, gasto, porcentaje | Ver gastos | límite exacto 100 |
| `budget_near_limit` | `total_planned > 0` y `threshold <= percentage_used < 100` | warning | 30 | porcentaje | Ver gastos | umbral 90–99,99 |
| `pending_payments` | `planned_pending_amount > 0` | warning | 40 | pendiente total | Ver pagos | pendiente positivo |
| `missing_income` | ingreso cero, existe gasto o plan y periodo no futuro | info | 50 | ingreso, gasto, plan, periodo | — | no se marca critical |
| `insufficient_data` | ingreso, gasto y plan son cero | info | 60 | totales mínimos | — | periodo vacío |

Orden: severidad (`critical`, `warning`, `info`), prioridad y código. Se deduplica por código. La respuesta inicial muestra como máximo dos. Si existen más, `action_group` añade `other_alerts_detail`; ese detalle las presenta en tabla para no violar el máximo global de alert blocks.

## Alertas pospuestas

- `overdue_payments`: el dominio no aporta todavía una regla de vencimiento mensual inequívoca para todas las obligaciones.
- `category_increase`: requiere base histórica y umbral que evite porcentajes engañosos sobre importes pequeños.
- `future_negative_balance`: requiere una proyección determinista que no existe.

No se generan recomendaciones ni lenguaje alarmista adicional. `critical` solo aparece con evidencia objetiva de caja o ejecución presupuestaria.
