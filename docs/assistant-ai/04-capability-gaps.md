# Carencias priorizadas

## Resumen

| Prioridad | Cantidad | Interpretación |
|---|---:|---|
| P0 | 1 | Puede producir un presupuesto incompleto hoy |
| P1 | 6 | Alto valor o control necesario para un MVP fiable |
| P2 | 4 | Mejora relevante de eficiencia/UX |
| P3 | 1 | Optimización futura |

## P0

### G-01 — Planes nuevos ONE_MONTH omitidos del presupuesto

- **Pregunta afectada:** “¿Cómo está mi presupuesto de septiembre?”
- **Motivo:** `PlannedExpensePlanViewSet` permite crear `plan_type=ONE_MONTH`, incluido desde el frontend, pero `BudgetService.get_planned_plans_summary()` filtra `plan_type="ONGOING"`. Solo los legacy `PlannedExpense` se agregan por la otra rama.
- **Datos faltantes:** no faltan; falta incluir la fuente correcta sin duplicar filas migradas.
- **Solución:** corregir service/regla de deduplicación y añadir pruebas; no requiere endpoint nuevo.
- **Backend:** medio, lógica financiera sensible.
- **Frontend:** ninguno si se conserva el contrato.
- **Riesgo de contrato:** medio; cambiarán totales que hoy pueden estar incorrectos.
- **Alternativa temporal:** no afirmar exactitud total si hay planes nuevos ONE_MONTH; consultar planes y advertir, pero no sumar en el modelo.

## P1

### G-02 — Resumen mensual sin ingresos reales ni balance de caja

- **Pregunta:** “¿Cuál es mi saldo real del mes?”
- **Motivo/datos:** budget no agrega `Income`; balance se calcula en frontend.
- **Solución:** ampliar DTO mediante nuevo endpoint agregado o serializer de resumen; preferible service `MonthlyFinancialSummaryService` y endpoint semántico, sin cambiar `/budget/` inicialmente.
- **Impacto:** backend medio, frontend opcional; riesgo bajo por contrato aditivo.
- **Alternativa:** tool suma `/incomes/` y resta `actual_spent` con Decimal.

### G-03 — Ambigüedad de `remaining_amount`

- **Pregunta:** “¿Cuánto dinero me queda?”
- **Motivo:** el campo significa `total_planned-total_spent`, no caja disponible.
- **Solución:** DTO/tool con `budget_variance` y `cash_balance`; mantener alias existente para compatibilidad.
- **Impacto:** backend bajo; frontend bajo; riesgo bajo si es aditivo.
- **Alternativa:** desambiguar lenguaje y etiquetar siempre.

### G-04 — Sin agregación por categoría/pagador

- **Preguntas:** “¿En qué gastamos más?”, “¿Cuánto pagó cada persona?”
- **Motivo:** frontend agrupa listas completas.
- **Solución:** endpoint agregado o acción read-only con `group_by=category|payer`, periodo obligatorio y resultados Decimal.
- **Impacto:** backend medio, frontend positivo; riesgo bajo.
- **Alternativa:** composición tool sobre `/expenses/?year&month`.

### G-05 — Sin rango histórico/compare estable

- **Pregunta:** “Compara los últimos seis meses.”
- **Motivo:** solo filtros de un mes exacto; múltiples llamadas y efectos laterales.
- **Solución:** nuevo service y endpoint de series/compare con `from_year/from_month/to_year/to_month`, máximo de meses.
- **Impacto:** backend medio-alto; frontend opcional; riesgo bajo aditivo.
- **Alternativa:** limitar MVP a dos meses y componer snapshots.

### G-06 — Falta zona horaria por usuario

- **Pregunta:** “¿Cuánto gasté este mes?” cerca de cambio de mes.
- **Motivo:** backend solo tiene `TIME_ZONE` global; frontend usa zona del navegador; Profile no guarda timezone.
- **Solución:** nueva preferencia de usuario/modelo o política de timezone de familia; normalizador común.
- **Impacto:** backend/frontend medio; riesgo bajo-aditivo.
- **Alternativa:** usar timezone de familia/configuración global declarada y mostrar periodo.

### G-07 — Escrituras sin idempotencia ni auditoría de dominio

- **Pregunta:** “Registra este gasto” ante reintentos.
- **Motivo:** POST CRUD crea de nuevo; no hay `Idempotency-Key`, draft ni log before/after.
- **Solución:** service/endpoint prepare+commit, clave idempotente por usuario/familia y audit event.
- **Impacto:** backend alto, frontend medio; riesgo bajo si se añade capa sin cambiar CRUD.
- **Alternativa:** MVP solo lectura.

## P2

### G-08 — Filtros de gastos e ingresos insuficientes

- **Pregunta:** “Gastos de alimentación entre dos fechas, mayores de 50 €.”
- **Motivo:** gastos solo `year+month,payer`; ingresos solo `year+month`.
- **Solución:** query params validados `date_from,date_to,category,payer,planning_status,min_amount,max_amount,ordering,limit`.
- **Impacto:** backend medio, frontend opcional; riesgo bajo.
- **Alternativa:** filtrar un único mes en tool.

### G-09 — Historial recurrente sin periodo ni paginación

- **Pregunta:** “Pagos del alquiler de 2026.”
- **Motivo:** `/payments/` devuelve todo.
- **Solución:** query params año/mes/rango y paginación o acción resumida.
- **Impacto:** backend bajo; riesgo medio si se cambia forma, por lo que debe ser aditivo/opt-in.
- **Alternativa:** filtrar respuesta si el volumen está acotado.

### G-10 — Categorías sin uso/tipo

- **Pregunta:** “¿Qué categorías de ingreso tengo?”
- **Motivo:** modelo no distingue; frontend usa heurísticas y termina aceptando categorías desconocidas en ambos contextos.
- **Solución:** nueva regla/modelo/serializer (`usage_type=income|expense|both`) tras decisión de producto.
- **Impacto:** backend/frontend medio-alto; riesgo medio por datos existentes.
- **Alternativa:** decir “categorías disponibles”, no “de ingreso/gasto”.

### G-11 — `GET` financieros con efectos laterales

- **Pregunta:** cualquier lectura de un mes inexistente.
- **Motivo:** budget, income plan month y month-status crean `Month`/occurrences.
- **Solución:** separar selector read-only de materialización o documentar/idempotentizar explícitamente; considerar creación lazy solo en escritura.
- **Impacto:** backend medio; frontend nulo; riesgo medio.
- **Alternativa:** aceptar efecto idempotente y trazarlo como `read_with_materialization`.

## P3

### G-12 — Forecast y alertas inteligentes

- **Pregunta:** “¿Cuánto gastaremos en diciembre?”
- **Motivo/datos:** no hay forecast, baseline, objetivos ni calidad histórica declarada.
- **Solución:** nuevo service/modelo de previsión e instrumentación, con intervalos de confianza y evaluación; no un prompt que extrapole.
- **Impacto:** alto en backend/datos; frontend nuevo; riesgo de producto alto.
- **Alternativa:** mostrar histórico factual sin pronóstico.

## Lo que no requiere endpoint nuevo todavía

- Top gastos, top categoría, total por pagador y balance de un único mes pueden componerse de forma segura dentro de tools.
- Completar/reabrir pagos ya tiene acciones canónicas.
- Listar categorías y miembros ya está resuelto.
- Comparar exactamente dos meses puede pilotarse con composición antes de construir series históricas.
