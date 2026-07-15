# Herramientas internas de lectura

El registro estático de `core/assistant/registry.py` contiene únicamente seis tools versión `1.0`, modo `read`, permiso `authenticated_family_member` y `requires_confirmation=false`. No existe API de registro dinámico ni herramienta de escritura.

Todas reciben `actor`, `family` y un objeto de argumentos. La identidad procede de la sesión y se vuelve a comprobar contra `actor.profile.family`. `user_id`, `family_id` y `owner_id` se rechazan; los IDs funcionales se resuelven siempre dentro de la familia. Los errores se convierten en `ToolResult` tipado.

## `get_monthly_budget`

- Propósito: presupuesto, pago, pendiente y desviación del mes.
- Argumentos: `year` 1..9999, `month` 1..12.
- Respuesta: `MonthlyBudgetSummary`.
- Servicio: `BudgetService(..., materialize=False)`.
- Permiso: miembro autenticado de la familia.
- Límite: un periodo.
- Errores: `invalid_arguments`, `permission_denied`, `tool_execution_failed`.
- Pruebas: importes separados, periodo, mes vacío, balance compatible y lectura sin escrituras.

## `get_monthly_cash_summary`

- Propósito: ingreso real, salidas reales y balance de caja.
- Argumentos: año y mes.
- Respuesta: `MonthlyCashSummary`.
- Servicio: mismo cálculo financiero canónico, sin recalcular en provider.
- Permisos/errores: iguales a presupuesto.
- Pruebas: caja positiva y negativa, no planificados y decimales.

## `list_monthly_expenses`

- Propósito: listar movimientos reales mínimos.
- Argumentos: año, mes, `category_id?`, `payer_id?`, `planned?`, `ordering?`, `limit?`.
- Orden permitido: `-amount`, `amount`, `-date`, `date`.
- Límite: 20 por defecto, 100 máximo; devuelve `has_more`, no cursores internos.
- Respuesta: `ExpenseListItem[]`.
- Query: queryset familiar con `select_related(category,payer,payer__profile)`.
- Validación: categoría y pagador deben pertenecer a la familia; IDs ajenos producen `resource_not_found` sin revelar existencia global.
- Pruebas: filtros, orden estable, límite, PII y una consulta para el listado sin filtros relacionales.

## `get_recurring_payment_status`

- Propósito: estados mensuales canónicos de pagos fijos.
- Argumentos: año y mes.
- Respuesta: `RecurringPaymentStatus[]`.
- Servicio: `BudgetService.get_recurring_summary(materialize=False)` y `calculate_recurring_payment_amounts`.
- Estado: usa `pending`, `partially_paid`, `covered`, `exceeded` o `completed`; no inventa estados.
- Pruebas: pago parcial, PII, periodo vacío y ausencia de materialización.

## `get_category_spending`

- Propósito: gasto real agrupado por categoría en backend.
- Argumentos: año, mes y `limit` (10 por defecto, 50 máximo).
- Respuesta: total, lista con importe/conteo/porcentaje, `has_more`.
- Query: `aggregate` + `values().annotate(Sum, Count)`; dos consultas acotadas.
- Pruebas: agregación, límite, periodo vacío y aislamiento.

## `get_payer_spending`

- Propósito: gasto real agrupado por pagador.
- Argumentos: año y mes.
- Respuesta: total y hasta 100 nombres visibles con importe/conteo/porcentaje.
- Query: agregación familiar en dos consultas; no carga usuarios ni emails individualmente.
- Pruebas: totales, nombre minimizado, mes vacío y aislamiento.

## Lectura pura y rendimiento

El endpoint público de presupuesto mantiene por compatibilidad su materialización histórica de `Month` y occurrences. Las tools pasan `materialize=False`: consultan occurrences existentes para respetar estados, pero no crean meses ni estados durante un GET del asistente. Esto está cubierto tanto para un mes inexistente como para uno existente.

Las listas son acotadas. Las agregaciones se ejecutan en PostgreSQL/Django ORM y los detalles usan `select_related`, evitando cálculos financieros en React o en el provider.
