# Catálogo cerrado de intents

`INTENT_REGISTRY` es inmutable y contiene doce intents. Las frases nunca se usan como nombre interno.

| Intent | Tipo | Ejemplos | Tools principales | Bloques |
|---|---|---|---|---|
| `monthly_summary` | inicial | Cómo vamos, resumen del mes, estado de julio | budget, cash | summary, 4 métricas, hasta 2 alertas, acciones |
| `monthly_summary_detail` | detalle | acción Ver más | budget, cash, categories, expenses, recurring | categorías, gastos, pendientes, histórico si hay datos |
| `monthly_spending` | inicial | Cuánto hemos gastado | budget, cash | resumen, métricas, alertas aplicables, acción |
| `monthly_expenses_detail` | detalle | Ver gastos | expenses | tabla limitada a 10 |
| `monthly_cash_balance` | inicial | Cuánto dinero queda, balance de caja | budget, cash | resumen, ingresos/gastos/balance, alertas |
| `pending_payments` | inicial | Qué pagos faltan, cuánto queda pendiente | budget, recurring, cash | total, fijos pendientes, tabla de 5, alerta |
| `pending_payments_detail` | detalle | Ver pagos | recurring | tabla de hasta 10 pagos fijos pendientes |
| `category_spending` | inicial | En qué categoría gastamos más | categories | resumen, barras de hasta 5, acción |
| `category_spending_detail` | detalle | Ver más categorías | categories | barras de hasta 10 |
| `payer_spending` | inicial | Cuánto pagó cada persona | payers | resumen, barras sin IDs/PII, acción |
| `payer_spending_detail` | detalle | Ver reparto | payers | barras de hasta 10 personas |
| `other_alerts_detail` | detalle | Ver otras alertas | budget, cash | tabla de alertas evaluadas |

Solo confianza `high` ejecuta el motor desde texto. Los intents de detalle se reciben como `{intent, arguments:{year,month}}`; cualquier nombre no registrado devuelve `unsupported_intent`.
