# Contrato de métricas financieras mensuales

Fuente: `BudgetService.build_budget()`. El periodo es siempre una familia, año y mes. Los importes proceden de modelos y servicios Django; el proveedor o modelo de IA no los recalcula.

## Definiciones

| Campo real | Fórmula | Significado | Incluye ingresos | Incluye no planificados | Puede ser negativo | Etiqueta UX |
|---|---|---|---|---|---|---|
| `total_planned` | suma de importes efectivos de recurrentes + planes legacy + planes versionados | obligaciones planificadas del mes | No | No | No en datos válidos | Total planificado |
| `planned_paid_amount` | movimientos reales vinculados a obligaciones recurrentes o planificadas | parte pagada de obligaciones planificadas | No | No | No | Pagado de lo planificado |
| `recurring_pending_amount` | suma del pendiente canónico de recurrentes | recurrentes aún pendientes; completar explícitamente fuerza pendiente cero | No | No | No | Pagos fijos pendientes |
| `planned_pending_amount` | pendiente canónico de recurrentes + planes | todas las obligaciones planificadas pendientes | No | No | No | Pendiente planificado |
| `total_pending_amount` | igual que `planned_pending_amount` | alias heredado compatible | No | No | No | Pendiente planificado |
| `unplanned_total` | suma de gastos sin enlace plan/recurrente | salidas reales no planificadas | No | Sí, exclusivamente | No | Gasto no planificado |
| `total_spent` | `planned_paid_amount + unplanned_total` | todas las salidas reales del mes | No | Sí | No | Gasto real total |
| `actual_spent` | igual que `total_spent` | alias explícito compatible | No | Sí | No | Gasto real total |
| `remaining_amount` | `total_planned - total_spent` | desviación presupuestaria heredada; no es dinero disponible | No | Sí | Sí | Desviación del presupuesto |
| `difference_amount` | igual que `remaining_amount` | alias heredado de desviación | No | Sí | Sí | Desviación del presupuesto |
| `budget_variance` | igual que `remaining_amount` | nombre inequívoco añadido de forma compatible | No | Sí | Sí | Desviación del presupuesto |
| `actual_income` | suma de `Income.amount` del periodo familiar | entradas reales registradas | Sí, solo reales | No | No | Ingresos reales |
| `cash_balance` | `actual_income - total_spent` | saldo real mensual de caja según movimientos registrados | Sí, reales | Sí | Sí | Balance de caja |
| `percentage_used` | `total_spent / total_planned * 100`; 0 si ambos son cero; 100 si no hay plan y sí gasto | ejecución respecto del presupuesto | No | Sí | No | Ejecución del presupuesto |

No existen campos públicos llamados `total_income`, `balance`, `planned_paid` o `planned_pending`. Los equivalentes implementados son `actual_income`, `cash_balance`, `planned_paid_amount` y `planned_pending_amount`.

## Matices canónicos

- Un pago parcial aumenta `planned_paid_amount` y reduce el pendiente.
- Un pago por encima del plan puede hacer negativa la desviación, pero el pendiente se limita a cero.
- Marcar una occurrence como completada fuerza su pendiente a cero sin crear ni alterar movimientos. `difference_amount` del ítem conserva la diferencia aritmética entre plan y pago.
- `unplanned_total` ya está incluido en `total_spent`; no debe sumarse otra vez.
- `remaining_amount` nunca debe presentarse como «dinero que queda».
- El producto no almacena moneda por familia. Los DTOs usan por ahora `DEFAULT_CURRENCY`, cuyo valor seguro por defecto es `EUR`; esto es configuración, no conversión monetaria.

## Ejemplo

Con 2.450 planificados, 1.760 pagados contra planes, 180 no planificados y 3.200 de ingresos reales:

- `planned_pending_amount = 690.00`
- `total_spent = 1,940.00`
- `budget_variance = 510.00`
- `cash_balance = 1,260.00`
- `percentage_used = 79.18`

Desviación, pendiente y caja son conceptos distintos aunque algunos valores coincidan en casos simples.

## Compatibilidad

No se eliminó ni renombró ningún campo. Los nuevos campos son aditivos y cuentan con prueba de contrato. Los DTOs del asistente prefieren los nombres inequívocos y no exponen `remaining_amount`.
