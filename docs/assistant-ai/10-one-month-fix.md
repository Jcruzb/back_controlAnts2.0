# Corrección de planes `ONE_MONTH`

## Error y causa raíz

`BudgetService.get_planned_plans_summary()` consultaba únicamente `PlannedExpensePlan.plan_type="ONGOING"`. El serializer permite crear planes `ONE_MONTH`, por lo que un plan puntual nuevo, sin una fila legacy paralela, no aparecía en el presupuesto de ningún mes.

`ONE_MONTH` significa una obligación versionada aplicable exclusivamente al mes definido por `start_month` y `end_month` (ambos coinciden). El mes financiero lo determina ese rango, no `created_at` ni la zona horaria de creación.

## Escenario reproducible

1. Crear un plan `ONE_MONTH` con inicio y fin en septiembre de 2026 e importe 100 EUR.
2. Registrar un movimiento vinculado de 40 EUR.
3. Consultar agosto, septiembre y octubre.

Antes de la corrección, septiembre devolvía cero filas del plan, `total_planned=0` y el movimiento se trataba de hecho como gasto contra un presupuesto omitido. Agosto y octubre tampoco lo incluían.

## Comportamiento corregido

- Se consideran todos los planes activos cuyo rango y versión son efectivos en el periodo.
- El plan puntual aparece exactamente una vez en septiembre, con 100 planificados, 40 pagados y 60 pendientes.
- No aparece en agosto ni octubre.
- Los movimientos vinculados alimentan `paid_amount` y `total_spent`; un plan sin movimientos sigue alimentando `total_planned` y el pendiente.
- La consulta está aislada por familia.
- La fecha de creación y la zona horaria no cambian el mes objetivo.

La migración `0011_migrate_planned_expenses_to_plans` creó espejos `ONE_MONTH` de filas `PlannedExpense` legacy. Para no duplicar históricos, el servicio conserva la fila legacy como fuente financiera cuando encuentra una firma exacta de categoría, nombre, importe y creador en el mismo mes. Un plan nuevo sin ese espejo sí se agrega. Las occurrences siguen protegidas por sus constraints y las consultas repetidas no duplican importes ni filas.

## Archivos modificados

- `core/services/budget_service.py`
- `core/tests.py`

## Pruebas añadidas

- inclusión única en el mes objetivo y exclusión del anterior/posterior;
- sin movimientos, pago parcial y pago completo;
- espejo legacy migrado y consultas repetidas sin duplicación;
- creación anterior o durante el mes objetivo;
- aislamiento entre familias;
- independencia respecto de `created_at` y zona horaria;
- consistencia de totales, pendiente, desviación y caja.

## Impacto y despliegue

No cambia la forma del contrato ni requiere migración. Sí corrige los totales de meses que ya tengan planes `ONE_MONTH` nuevos omitidos; por tanto, tras desplegar pueden aumentar `total_planned` y `planned_pending_amount`, y cambiar la desviación/porcentaje. Los gastos reales y el saldo de caja no se inventan ni se duplican.

Despliegue recomendado: ejecutar la suite, desplegar el cambio de servicio, comparar uno o dos meses con planes puntuales conocidos y monitorizar errores del presupuesto. No se requiere backfill.
