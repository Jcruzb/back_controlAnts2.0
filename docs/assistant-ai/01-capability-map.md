# Mapa de capacidades

> Fotografía de la auditoría inicial. Los estados P0 y las carencias de caja/agregación aquí descritos fueron tratados en fase 2; para el contrato vigente véanse `10-one-month-fix.md` a `15-assistant-endpoint.md`.

## Escala de preparación

- **Alta:** contrato backend directo, aislado y con semántica estable.
- **Media:** combinación determinista de respuestas actuales o contrato con ambigüedad/adaptación.
- **Baja:** escritura, lógica interna sensible o riesgo elevado.
- **No disponible:** falta dato, regla o contrato fiable.

| # | Capacidad | Fuente | Endpoint(s) | Parámetros | Dato directo | Composición permitida | Riesgo de interpretación | Preparación |
|---:|---|---|---|---|---|---|---|---|
| 1 | Presupuesto mensual | `BudgetService` | `GET /budget/` | año, mes | Sí: planificado, gastado, pendientes, diferencia, estados | Ordenar/filtrar filas | `remaining_amount` no es saldo de caja; P0 ONE_MONTH | Media |
| 2 | Ejecución y desviación del presupuesto | `BudgetService._calculate_status` | `GET /budget/` | año, mes | Sí | Explicar `status`/porcentaje | porcentaje puede superar 100; UI lo limita visualmente | Alta |
| 3 | Balance mensual real | `Income` + gastos | `/incomes/` + `/budget/` o `/expenses/` | año, mes | No | Sumar ingresos y restar `actual_spent` | No llamar a esto `remaining_amount` | Media |
| 4 | Ingresos reales | `Income` | `GET /incomes/` | año+mes | Movimientos sí; total no | Suma Decimal determinista | Frontend usa Number; tool debe usar Decimal | Media |
| 5 | Ingresos planificados | `IncomePlan/Version` | `GET /income-plans/month/` o bloque de budget | año, mes | Sí: estado e importe efectivo | Filtrar pending/resolved | `MISSING_VERSION` no equivale a cero | Alta |
| 6 | Gastos reales | `Expense` | `GET /expenses/` | año+mes, pagador | Sí | Ordenar, top-N, sumar | Sin filtros server-side por categoría/tipo | Alta |
| 7 | Gastos planificados legacy | `PlannedExpense` | `/planned-expenses/`, `/budget/` | ID o año/mes vía budget | Sí en budget | Filtrar/ordenar | Sistema paralelo al nuevo | Media |
| 8 | Gastos planificados versionados | Plan + Version | `/planned-expense-plans/`, `/budget/` | ID/periodo | Ongoing sí | Resolver versión por periodo solo en backend | Nuevos ONE_MONTH omitidos del budget | Baja hasta corregir P0 |
| 9 | Gastos no planificados | enlaces nulos de `Expense` | `/budget/` + `/expenses/` | año, mes | Total sí; detalle no filtrado | Filtrar movimientos con tres enlaces nulos | No sumar `unplanned_total` otra vez a `total_spent` | Media |
| 10 | Pagos recurrentes/fijos | `RecurringPayment` | `/recurring-payments/`, `/budget/` | periodo en budget | Definiciones y estado sí | Combinar nombre/fecha con estado | Lista de definiciones incluye inactivos | Alta |
| 11 | Estado mensual recurrente | occurrence + service | `/recurring-payments/{id}/month-status/` | ID, año, mes | Sí | Resumir | completar no crea movimiento | Alta lectura / Media escritura |
| 12 | Estado mensual planificado | occurrence + service | acciones `month-status` legacy/nueva | ID, año, mes | Sí | Resumir | misma semántica de completado manual | Alta lectura / Media escritura |
| 13 | Categorías | `Category` | `/categories/` | — | Sí | Mostrar/ordenar | No hay tipo ingreso/gasto | Alta lectura |
| 14 | Pagadores/personas | `User/Profile` + `Expense.payer` | `/family/members/`, `/expenses/` | periodo, payer opcional | Identidad y movimientos sí | Agrupar total por payer | `user` creador no es `payer`; PII excesiva | Media |
| 15 | Familia y roles | `Profile/Family` | `/auth/me/`, `/family/members/` | — | Nombre/id/rol sí | — | No existe gestión familiar API | Media |
| 16 | Comparación entre meses | dos snapshots | 2×`/budget/`, 2×`/incomes/` | periodos A/B | No agregada | Diferencias de campos homólogos | Multiplica llamadas y efectos laterales GET | Media |
| 17 | Comparación entre categorías | gastos mensuales | `/expenses/` + `/categories/` | año, mes | No agregada | group-by y ranking Decimal | Categorías renombradas/histórico | Media |
| 18 | Tendencias y alertas | histórico mensual | múltiples listas/budgets | rango | No | Posible para pocos meses | Sin endpoint rango, baseline ni regla de alerta | Baja |
| 19 | CRUD de movimientos | viewsets | `/expenses/`, `/incomes/` y detalle | payload | Sí | Ninguna lógica financiera en modelo | confirmación, duplicados, mes cerrado | Baja |
| 20 | Configuración/acciones | categorías, planes, estados | endpoints admin y `month-status` | IDs/payload | Sí | Solo previsualizar | impacto histórico/futuro y permisos | Baja |

## Composiciones seguras actuales

Estas operaciones son deterministas, pero deben vivir en una tool/backend, no en el prompt:

1. `total_income = sum(Income.amount)` para un mes completo.
2. `cash_balance = total_income - budget.actual_spent`.
3. top gastos = ordenar `Expense.amount` descendente.
4. gasto por categoría = agrupar gastos por `category` y sumar Decimal.
5. gasto por pagador = agrupar por `payer`/`payer_detail`, preservando `Sin asignar`.
6. comparación mensual = restar campos homólogos de dos snapshots etiquetados.

No son seguras como inferencia libre: pronósticos, recomendaciones de ahorro, causalidad de desviaciones, clasificación semántica por descripción o redefinición de qué es saldo disponible.

## Casos mínimos verificados

| Caso | Resultado actual | Evidencia |
|---:|---|---|
| 1. Presupuesto de septiembre | Respondible con año explícito | `BudgetView` valida periodo y usa `BudgetService` |
| 2. Gastado este mes | Respondible | `actual_spent/total_spent` en budget |
| 3. Dinero que queda | Parcial/ambiguo | budget solo da desviación; balance requiere ingresos |
| 4. Ingresado | Respondible por suma de `/incomes/` | `IncomeViewSet`, misma composición en frontend |
| 5. Gastos más altos | Respondible por ordenar lista mensual | `ExpenseViewSet` devuelve mes completo sin paginar |
| 6. Categoría con más gasto | Respondible por group-by | Dashboard realiza esa agrupación |
| 7. Fijos pendientes | Respondible | `budget.recurring[].pending_amount/payment_status` |
| 8. Recurrentes completados | Respondible | `is_completed/payment_status` |
| 9. Pagado de planificado | Respondible | `budget.planned[].paid_amount` |
| 10. Pendiente | Respondible si se identifica obligación | canonical pending service |
| 11. Quién pagó | Respondible | `Expense.payer_detail` |
| 12. Cuánto por persona | Respondible por group-by mensual | payer filter + frontend payerSummary |
| 13. No planificados | Total directo; detalle por filtrado cliente/tool | `unplanned_total` y enlaces nulos |
| 14. Comparar mes anterior | Parcial, 4 llamadas para incluir balance | no endpoint agregado |
| 15. Registrar gasto | Técnicamente sí; no en MVP | `POST /expenses/` |
| 16. Editar/eliminar gasto | Técnicamente sí; alto riesgo | detalle Expense + reglas de mes |
| 17. Completar pago fijo | Sí con confirmación | PATCH `month-status` |
| 18. Categorías existentes | Sí | GET `/categories/` |
| 19. Crear categoría | Sí solo admin | Admin/R + POST |
| 20. Situación familiar general | Parcial | requiere budget + incomes + agregaciones; P0 puede sesgar planificado |

## Evidencia del frontend

- `Dashboard.jsx` suma ingresos/gastos, calcula balance, agrupa por categoría, pagador y día.
- `Budget.jsx` prioriza `budget.actual_spent`, suma ingresos, calcula balance y clasifica gastos variables.
- `budgetSummary.js` calcula proyección, balance y porcentaje en cliente.
- `api.js` normaliza arrays/envelopes y gestiona sesión/CSRF.

Esto confirma que los datos base existen, pero también que balance, breakdowns y tendencias aún no son contratos financieros backend.
