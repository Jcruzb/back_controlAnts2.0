# DTOs estables del asistente

Los DTOs viven en `core/assistant/dto.py`. Son adaptadores internos, no serializers CRUD. Convierten dinero y porcentajes a strings decimales de dos posiciones, incluyen periodo explícito y moneda configurada, y reducen PII.

| DTO | Propósito | Campos principales | Datos excluidos |
|---|---|---|---|
| `MonthlyBudgetSummaryDTO` | presupuesto, pago, pendiente y desviación | `period`, `currency`, `planned`, `unplanned`, `budget` | IDs técnicos, movimientos, `remaining_amount` ambiguo |
| `MonthlyCashSummaryDTO` | entradas/salidas reales y caja | `period`, `currency`, `income.actual`, `outflows`, `cash_balance` | previsiones de ingreso y datos personales |
| `ExpenseListItemDTO` | detalle mínimo de gasto | `id`, nombre, importe, fecha, categoría, nombre visible del pagador, `is_planned` | email, username, perfil, familia, creador |
| `RecurringPaymentStatusDTO` | estado canónico mensual | importes planificado/pagado/pendiente/diferencia, completado y `payment_status` | email, occurrence ID, datos de autenticación |
| `CategorySpendingSummaryDTO` | agregación backend por categoría | categoría, icono, importe, conteo y porcentaje | movimientos individuales |
| `PayerSpendingSummaryDTO` | agregación backend por pagador | nombre visible, importe, conteo y porcentaje | email, rol, credenciales |

`period` tiene `year`, `month` numérico y etiqueta española determinista. La capa no interpreta expresiones relativas todavía; recibe año y mes ya normalizados.

## Contratos resumidos

`MonthlyBudgetSummary` separa:

```json
{
  "period": {"year": 2026, "month": 9, "label": "Septiembre de 2026"},
  "currency": "EUR",
  "planned": {"total": "2450.00", "paid": "1760.00", "pending": "690.00"},
  "unplanned": {"total": "180.00"},
  "budget": {"variance": "510.00", "percentage_used": "79.18", "status": "ok"}
}
```

`MonthlyCashSummary` devuelve únicamente hechos de caja:

```json
{
  "income": {"actual": "3200.00"},
  "outflows": {"total": "1940.00", "planned": "1760.00", "unplanned": "180.00"},
  "cash_balance": "1260.00"
}
```

Los tests cubren estructura, dos decimales, meses vacíos, balance negativo, etiqueta de periodo y ausencia de email. IDs de gasto/categoría/pagador se conservan solo donde permiten pedir detalle o aplicar un filtro familiar validado; nunca seleccionan tenant.
