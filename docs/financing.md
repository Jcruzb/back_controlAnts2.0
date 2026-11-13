# Tarjetas y compras financiadas

## Contrato

- `GET/POST /api/credit-accounts/`: nombre de tarjeta o cuenta, sin PAN, CVV ni credenciales.
- `GET/POST /api/financed-purchases/`: `name`, `category`, `credit_account` opcional, `purchase_date`, `total_amount` (total contractual a devolver), `installment_count` (1–360), `first_due_date`, `idempotency_key` UUID obligatorio. Repetir clave y contenido devuelve la misma compra y calendario (200); contenido diferente devuelve 409. La primera creación devuelve 201. La clave está aislada por familia y protegida por bloqueo transaccional y restricción única.
- La creación genera únicamente deuda y calendario mensual; no crea Expense. Cuotas de al menos un céntimo, resto en la última cuota; fechas 29–31 se acotan al último día del mes y recuperan el día original en meses posteriores.
- `POST /api/financing-installments/{id}/payments/`: `amount`, `date`, `payer` opcional (usuario actual por defecto), `idempotency_key` UUID. Pago parcial permitido, sobrepago rechazado. Repetir idéntica clave y contenido devuelve el Expense existente; cambiar contenido devuelve 409. Bloqueo de fila PostgreSQL serializa pagos concurrentes.
- Cada pago crea exactamente un Expense y afecta una sola vez a gasto real/cash_balance. Los gastos de financiación no admiten edición ni borrado por `/expenses/`.
- Administradores crean cuentas/compras; miembros de familia pueden consultar y registrar pagos. Categorías, cuentas, pagadores y cuotas se validan contra la familia autenticada. Mes de compra/pago cerrado rechaza nuevas operaciones.

## Límites explícitos de esta primera versión

No hay cálculo automático de intereses, extractos bancarios, límites de crédito, liquidación automática, amortización anticipada, cambios de calendario ni corrección/anulación de pagos. El total a devolver debe incluir intereses y comisiones conocidos. Las cuotas pendientes se muestran en Financiaciones y no se añaden al presupuesto de gastos planificados. Antes de confirmar un pago se revisan importe, fecha y pagador; la interfaz explica que queda protegido.

## Verificación

Ejecutar `python manage.py migrate`, `python manage.py test` sobre una base local PostgreSQL (prueba concurrente requiere bloqueos reales). Escenario: compra 100 € en tres cuotas desde 31 enero => 33,33 / 33,33 / 33,34, vencimientos 31 enero / 28 febrero / 31 marzo. No cambia gasto real al crear. Pagar 10 € reduce pendiente a 90 € y balance mensual en 10 €. Reintentar el mismo pago conserva un único gasto. Un miembro de otra familia no puede consultar ni pagar estas cuotas.

## Compatibilidad de creación (0021)

Las compras anteriores conservan su identidad y calendario con clave nula. Las nuevas solicitudes sin UUID se rechazan (400); no se genera una clave nueva en cada reintento, porque duplicaría deuda tras perder una respuesta. El frontend conserva y bloquea la solicitud mientras su resultado sea incierto, incluso si falla la recarga posterior al POST. Una respuesta 4xx definitiva permite corregir los datos. Actualizar ambos componentes juntos y aplicar la migración 0021 antes de probar la nueva creación.
