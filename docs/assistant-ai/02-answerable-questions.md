# Catálogo de preguntas respondibles

> Catálogo basado en la API previa a la fase 2. Las limitaciones `ONE_MONTH`, caja y agregaciones se conservan como evidencia histórica; las seis tools implementadas y sus contratos vigentes están en `11-financial-metrics-contract.md` y `13-read-tools-implementation.md`.

## Reglas comunes

- El periodo se resuelve en la zona horaria efectiva, se convierte a `year` y `month` numéricos y se repite en la respuesta.
- Las sumas y agrupaciones permitidas se ejecutan en código determinista con Decimal, nunca por aritmética libre del modelo.
- Los IDs de familia/usuario no proceden de la conversación. Los resuelve la sesión.
- `Respondible` incluye operaciones de escritura que la API soporta, aunque se pospongan del MVP y requieran confirmación.
- Conteo: **27 respondibles, 4 parcialmente respondibles y 3 no respondibles**.

## Estado del presupuesto

### ¿Cómo está mi presupuesto de septiembre de 2026?

**Intención funcional:** estado mensual. **Herramienta o endpoint:** `GET /api/budget/?year=2026&month=9`. **Parámetros:** año 2026, mes 9. **Conversación:** si solo dice septiembre, usar el año contextual o pedirlo si hay riesgo de equivocación. **Respuesta actual:** planificado, gasto real, pendientes, variación, porcentaje, estado y detalle fijo/planificado. **Transformación permitida:** resumir, ordenar y explicar campos. **Limitaciones:** no contiene ingresos reales y puede omitir planes nuevos `ONE_MONTH` hasta corregir P0. **Estado:** Parcialmente respondible.

### ¿Cuánto he gastado este mes?

**Intención funcional:** gasto real mensual. **Endpoint:** `GET /api/budget/`. **Parámetros:** periodo resuelto. **Conversación:** zona horaria y fecha actual. **Respuesta actual:** `actual_spent`/`total_spent`. **Transformación:** formato monetario; no volver a sumar `unplanned_total`. **Limitaciones:** ninguna salvo P0 no afecta gasto ya registrado, solo presupuesto. **Estado:** Respondible.

### ¿Cuánto dinero me queda?

**Intención funcional:** desambiguar variación presupuestaria frente a saldo de caja. **Endpoints:** `/budget/` y, si pide caja, `/incomes/`. **Parámetros:** periodo. **Conversación:** aclarar solo si el contexto no distingue “del presupuesto” o “en balance”. **Respuesta actual:** `remaining_amount` para presupuesto; suma de ingresos menos `actual_spent` para balance. **Transformación:** composición Decimal etiquetada. **Limitaciones:** no hay campo backend de balance real. **Estado:** Parcialmente respondible.

### ¿Cuál es la situación general de mi economía familiar?

**Intención funcional:** resumen mensual integral. **Endpoints:** `/budget/`, `/incomes/`, opcional `/expenses/`. **Parámetros:** periodo. **Conversación:** periodo obligatorio/resuelto. **Respuesta actual:** presupuesto, gasto, ingresos por composición, balance, pendientes y categorías mediante composición. **Transformación:** resumen breve y hechos separados de interpretación. **Limitaciones:** varias llamadas, agregaciones cliente/tool y P0 `ONE_MONTH`. **Estado:** Parcialmente respondible.

## Ingresos

### ¿Cuánto hemos ingresado en septiembre?

**Intención funcional:** total de ingresos reales. **Endpoint:** `GET /api/incomes/?year=Y&month=M`. **Parámetros:** periodo. **Conversación:** año seguro. **Respuesta actual:** lista mensual completa. **Transformación:** sumar `amount` con Decimal. **Limitaciones:** no hay total agregado backend. **Estado:** Respondible.

### ¿Qué ingresos registramos este mes?

**Intención funcional:** listado de ingresos. **Endpoint:** `/incomes/?year&month`. **Parámetros:** periodo. **Respuesta actual:** importe, fecha, descripción, categoría, plan y metadatos. **Transformación:** ordenar, limitar y resumir. **Limitaciones:** sin filtro server por categoría. **Estado:** Respondible.

### ¿Qué ingresos planificados siguen pendientes?

**Intención funcional:** planes de ingreso no materializados. **Endpoint:** `GET /income-plans/month/?year&month` o `budget.income_plan_month`. **Parámetros:** periodo. **Respuesta actual:** filas `PENDING`, `RESOLVED`, `MISSING_VERSION` y `can_resolve`. **Transformación:** filtrar `PENDING`; mostrar `MISSING_VERSION` como dato faltante. **Limitaciones:** GET crea Month si no existe. **Estado:** Respondible.

## Gastos

### ¿Cuáles son los gastos más altos del mes?

**Intención funcional:** ranking de movimientos. **Endpoint:** `GET /expenses/?year&month`. **Parámetros:** periodo y límite interno acotado. **Respuesta actual:** mes completo. **Transformación:** ordenar Decimal descendente y tomar top-N. **Limitaciones:** no hay `ordering`/`limit` server. **Estado:** Respondible.

### ¿Qué gastos tuve el 12 de septiembre?

**Intención funcional:** filtrar por día. **Endpoint:** `/expenses/?year=2026&month=9`. **Parámetros:** periodo y día 12 en tool. **Respuesta actual:** movimientos con fecha. **Transformación:** filtro exacto determinista. **Limitaciones:** no hay `date` query param. **Estado:** Respondible.

### ¿Qué gastos no estaban planificados?

**Intención funcional:** detalle variable/no vinculado. **Endpoints:** `/expenses/?year&month` y `/budget/`. **Parámetros:** periodo. **Respuesta actual:** total `unplanned_total`; movimientos contienen tres enlaces. **Transformación:** seleccionar donde `planned_expense`, `planned_expense_plan` y `recurring_payment` sean null. **Limitaciones:** no existe filtro server. **Estado:** Respondible.

### Enséñame el detalle del gasto 123

**Intención funcional:** consultar movimiento concreto. **Endpoint:** `GET /expenses/123/`. **Parámetros:** ID opaco devuelto previamente, no inventado. **Respuesta actual:** importe, categoría, pagador, fecha, enlaces y estados mensuales. **Transformación:** redactar campos internos. **Limitaciones:** 404 si no pertenece a la familia. **Estado:** Respondible.

## Pagos fijos

### ¿Qué pagos fijos faltan por completar?

**Intención funcional:** obligaciones recurrentes pendientes. **Endpoint:** `/budget/?year&month`. **Parámetros:** periodo. **Respuesta actual:** `recurring[]` con pendiente y estado. **Transformación:** filtrar no completados con pendiente/estado correspondiente. **Limitaciones:** “completado” puede ser decisión manual aunque pago sea parcial. **Estado:** Respondible.

### ¿Qué pagos recurrentes ya están completados?

**Intención funcional:** recurrentes cerrados manualmente. **Endpoint:** `/budget/`. **Parámetros:** periodo. **Respuesta actual:** `is_completed` y `payment_status=completed`. **Transformación:** filtrar y explicar diferencia entre completado/cubierto. **Limitaciones:** ninguna adicional. **Estado:** Respondible.

### ¿Cuánto se ha pagado y cuánto falta de la hipoteca?

**Intención funcional:** estado de un recurrente concreto. **Endpoint:** `GET /recurring-payments/{id}/month-status/?year&month`. **Parámetros:** ID resuelto por búsqueda/lista y periodo. **Respuesta actual:** planificado, pagado, pendiente, diferencia y estado. **Transformación:** ninguna financiera. **Limitaciones:** nombres no son filtro; tool debe resolver coincidencias y pedir aclaración si hay varias. **Estado:** Respondible.

### Muéstrame el historial de pagos del alquiler

**Intención funcional:** movimientos asociados al recurrente. **Endpoint:** `/recurring-payments/{id}/payments/`. **Parámetros:** ID. **Respuesta actual:** definición y todos los `payments[]`. **Transformación:** ordenar/agrupar por mes. **Limitaciones:** sin periodo ni paginación, potencialmente grande. **Estado:** Respondible.

## Gastos variables y categorías

### ¿Cuánto gastamos fuera de lo planificado?

**Intención funcional:** total no planificado. **Endpoint:** `/budget/`. **Parámetros:** periodo. **Respuesta actual:** `unplanned_total`. **Transformación:** formato monetario. **Limitaciones:** no confundir con `total_spent`. **Estado:** Respondible.

### ¿Cómo evolucionó el gasto día a día este mes?

**Intención funcional:** serie diaria. **Endpoint:** `/expenses/?year&month`. **Parámetros:** periodo. **Respuesta actual:** fechas e importes. **Transformación:** group-by día y suma Decimal, como Dashboard. **Limitaciones:** no contrato agregado server; no inferir tendencia causal. **Estado:** Respondible.

### ¿Qué categorías existen?

**Intención funcional:** catálogo configurable. **Endpoint:** `GET /categories/`. **Parámetros:** ninguno. **Respuesta actual:** id, nombre, icono, color y descripción. **Transformación:** ordenar/presentar. **Limitaciones:** no distingue ingreso/gasto. **Estado:** Respondible.

### ¿En qué categoría gastamos más?

**Intención funcional:** ranking por categoría. **Endpoints:** `/expenses/?year&month`, opcional `/categories/`. **Parámetros:** periodo. **Respuesta actual:** cada gasto trae ID de categoría. **Transformación:** group-by y suma Decimal. **Limitaciones:** agregación no existe en backend. **Estado:** Respondible.

### ¿Puedo crear una categoría “Mascotas”?

**Intención funcional:** crear configuración. **Endpoint:** `POST /categories/`. **Parámetros:** nombre, icono, color, descripción. **Conversación:** mostrar payload y comprobar rol admin antes de confirmar. **Respuesta actual:** recurso creado o 403/validación. **Transformación:** solo preparar/validar. **Limitaciones:** fuera de MVP de lectura; unicidad por familia. **Estado:** Respondible.

## Comparativas

### ¿Cómo se compara este mes con el anterior?

**Intención funcional:** comparación mensual general. **Endpoints:** dos `/budget/` y dos `/incomes/`. **Parámetros:** periodos resueltos. **Respuesta actual:** snapshots comparables. **Transformación:** diferencias de campos homólogos con Decimal. **Limitaciones:** cuatro llamadas, GET con efectos laterales, P0 y sin contrato compare. **Estado:** Parcialmente respondible.

### ¿Gastamos más en alimentación o vivienda?

**Intención funcional:** comparar categorías en un periodo. **Endpoint:** `/expenses/?year&month`. **Parámetros:** periodo y categorías resueltas desde catálogo. **Transformación:** group-by y comparación Decimal. **Limitaciones:** nombres ambiguos requieren IDs. **Estado:** Respondible.

### ¿Cuál fue la tendencia de gasto de los últimos doce meses?

**Intención funcional:** serie histórica anual. **Endpoint:** no existe endpoint de rango; requeriría 12 llamadas/listados. **Parámetros:** fin de rango. **Respuesta actual:** técnicamente reconstruible, pero sin contrato eficiente ni garantías operativas para una tool inicial. **Limitaciones:** N+1, efectos laterales y volumen. **Estado:** No respondible de forma correcta/estable para el MVP.

### ¿Cuánto gastaremos aproximadamente en diciembre?

**Intención funcional:** forecast. **Endpoint:** ninguno. **Datos faltantes:** modelo/regla de previsión, histórico normalizado, estacionalidad y confianza. **Transformación permitida:** ninguna inferencia numérica inventada. **Estado:** No respondible.

## Personas que pagan

### ¿Quién pagó este gasto?

**Intención funcional:** pagador real. **Endpoint:** `/expenses/{id}/`. **Parámetros:** ID. **Respuesta actual:** `payer` y `payer_detail`. **Transformación:** mostrar `display_name`; no usar `user` creador como pagador. **Limitaciones:** payer puede ser null en datos antiguos. **Estado:** Respondible.

### ¿Cuánto ha pagado cada persona este mes?

**Intención funcional:** desglose por pagador. **Endpoints:** `/expenses/?year&month`, opcional `/family/members/`. **Parámetros:** periodo. **Transformación:** group-by payer y suma Decimal. **Limitaciones:** sin endpoint agregado; conservar grupo “Sin asignar”. **Estado:** Respondible.

## Planificación

### ¿Cuánto se ha pagado de un gasto planificado y cuánto queda pendiente?

**Intención funcional:** estado canónico de obligación. **Endpoint:** `month-status` legacy o nuevo, según tipo de fila retornada por budget. **Parámetros:** tipo, ID, año, mes. **Respuesta actual:** planificado, pagado, pendiente, diferencia y estado. **Transformación:** explicar, no recalcular. **Limitaciones:** P0 afecta descubrimiento de ONE_MONTH nuevo. **Estado:** Respondible.

### ¿Qué obligaciones tengo previstas para el próximo mes?

**Intención funcional:** planificación futura. **Endpoint:** `/budget/` del próximo mes. **Parámetros:** periodo calculado. **Respuesta actual:** recurring y planned aplicables. **Transformación:** ordenar por importe/categoría. **Limitaciones:** P0 ONE_MONTH y GET crea registros. **Estado:** Respondible.

## Acciones sobre movimientos

### Registra un gasto de 42 € en supermercado hoy

**Intención funcional:** crear gasto. **Endpoint:** `POST /expenses/`. **Parámetros:** importe, categoría resuelta, fecha, pagador opcional, enlace opcional. **Conversación:** previsualizar periodo/categoría/pagador/importe y confirmar. **Respuesta actual:** gasto creado. **Transformación:** preparar payload; no elegir enlace planificado por semejanza textual. **Limitaciones:** fuera del MVP, requiere idempotencia. **Estado:** Respondible.

### Cambia este gasto de 42 € a 45 €

**Intención funcional:** editar importe. **Endpoint:** `PATCH /expenses/{id}/`. **Parámetros:** ID e importe. **Conversación:** mostrar antes/después y confirmar explícitamente. **Respuesta actual:** recurso actualizado o bloqueo por mes cerrado/completado. **Limitaciones:** alto riesgo; sin deshacer/audit de dominio. **Estado:** Respondible.

### Elimina este gasto

**Intención funcional:** borrar movimiento. **Endpoint:** `DELETE /expenses/{id}/`. **Parámetros:** ID. **Conversación:** detalle completo y confirmación fuerte. **Respuesta actual:** 204. **Limitaciones:** irreversible, sin soft delete. **Estado:** Respondible.

### Marca el alquiler como completado este mes

**Intención funcional:** cerrar obligación recurrente. **Endpoint:** `PATCH /recurring-payments/{id}/month-status/?year&month` con `is_completed=true`. **Conversación:** mostrar planificado, pagado, diferencia y advertir que no crea gasto. **Respuesta actual:** estado actualizado. **Limitaciones:** mes cerrado lo impide. **Estado:** Respondible.

### Reabre el pago planificado de septiembre

**Intención funcional:** reabrir obligación planificada. **Endpoint:** PATCH al `month-status` correcto con `false`. **Conversación:** identificar tipo/ID/periodo y confirmar. **Respuesta actual:** pendiente recalculado por servicio. **Limitaciones:** dos sistemas de planificación; mes cerrado bloquea. **Estado:** Respondible.

### Cierra septiembre para que nadie pueda modificarlo

**Intención funcional:** cerrar mes contable. **Endpoint:** ninguno público. **Datos faltantes:** API, permiso/política, auditoría y confirmación reforzada. **Alternativa:** operación administrativa fuera del asistente. **Estado:** No respondible.

## Índice de evidencia técnica del catálogo

Cada ficha anterior apunta a uno de estos contratos o composiciones verificadas:

| Evidencia | Ubicación | Preguntas que respalda |
|---|---|---|
| Entrada y validación de presupuesto | `core/views/budget_view.py:114` | presupuesto, gastado, restante, situación general |
| Totales y semántica financiera | `core/services/budget_service.py:376` | gasto real, planificado, pendiente, no planificado |
| Queryset mensual/pagador de gastos | `core/views/expense_viewset.py:64` | listados, top, fecha, payer, categorías |
| Queryset mensual de ingresos | `core/views/income_viewset.py:20` | total/lista de ingresos |
| Estados recurrentes y su historial | `core/views/RecurringPayment_viewset.py:112`, `:141` | fijos pendientes/completados/historial |
| Estados planificados | `core/views/plannedExpense_viewset.py:54`, `core/views/planned_expense_plan_viewset.py:179` | pagado, pendiente, completar/reabrir |
| Categorías y miembros por familia | `core/views/category_viewset.py:15`, `core/views/family_member_view.py:15` | catálogo, pagadores |
| Balance, categoría, payer y día en cliente | frontend `src/pages/Dashboard.jsx:876`, `:880`, `:913`, `:934` | composiciones deterministas existentes |
| Suma de ingresos y resumen mensual en cliente | frontend `src/pages/IncomesList.jsx:203`, `src/utils/budgetSummary.js:10` | ingreso total, balance y presentación |
| Aislamiento/contratos probados | `core/tests.py:151`, `:181`, `:236`, `:339`, `:713`, `:1012`, `:1179`, `:1266` | tenant, payer, budget, estados y roles |
| Evidencia del P0 ONE_MONTH | `core/services/budget_service.py:202`, serializer `:125`, frontend `PlannedExpensePlanForm.jsx:24` | exactitud del presupuesto/planificación |
