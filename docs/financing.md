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

## Convertir un gasto ya pagado (0022)

`POST /api/expenses/{id}/convert-to-financing/` requiere administrador y confirmación
literal `confirmed: true`. El gasto representa dinero ya pagado: se conserva su ID,
importe, fecha, usuario, pagador, categoría, descripción, mes y vínculos. No se crea
otro Expense y el balance real no cambia. Se crea una compra con ese gasto como
pago inicial y se programa únicamente `total_amount - expense.amount`.

Petición: `confirmed`, `idempotency_key`, `name`, `total_amount`, `credit_account`
(ID o null), `installment_count`, `first_due_date` y `expected_expense`. Este último
es la instantánea exacta de los campos GET `amount`, `date`, `category`, `payer`,
`description`, `month`, `planned_expense`, `planned_expense_plan`,
`recurring_payment`, `is_recurring`. Otros campos se rechazan. Si algún dato cambió,
responde409 para obligar a recargar y revisar. La instantánea no se usa para editar.

Para esta conversión, `installment_count` cuenta cuotas pendientes (1–360) y su
primer vencimiento debe ser posterior a la fecha del gasto. Con total igual al
importe ya pagado se exige `installment_count: 0` y `first_due_date: null`: no hay
calendario pendiente. El total nunca puede ser menor al pago. La categoría se deriva
del gasto; únicamente si una importación histórica dejó su categoría nula se exige
`category` explícita para la compra, sin modificar la categoría original. No se
permite reclasificar un gasto existente durante la conversión.

Respuesta: PurchaseDTO,201 inicial o200 al repetir clave y contenido idénticos.
Clave reutilizada con otros datos o gasto ya vinculado devuelve409. Reintentar una
conversión ya completada no escribe, incluso si después se cerró el mes. Nuevas
conversiones rechazan meses cerrados y ocurrencias planificadas/recurrentes cerradas.
La categoría y tarjeta deben pertenecer a la familia; no se pueden convertir gastos
ajenos. El bloqueo de la familia protege claves y el del gasto serializa conversión,
edición y borrado. Estos últimos vuelven a consultar el vínculo tras obtener el
bloqueo, evitando usar relaciones cacheadas antes de esperar.

GET de gastos añade `financing: null | {purchase_id, credit_account,
is_initial_payment}`. PurchaseDTO añade `source_expense` y
`initial_payment: null | {expense_id, amount, date, payer}`. `installments` contiene
solo el calendario futuro, mientras `paid_amount` incluye el pago inicial y pagos
posteriores. Internamente el pago inicial usa la cuota número0 ya satisfecha y un
FinancingPayment que reutiliza el Expense original. Las cuotas normales siguen
numerándose desde1. La creación normal de compras conserva fecha obligatoria y
1–360 cuotas; no acepta el modo de cero cuotas.

La migración0022 es aditiva salvo ampliar el rango permitido de cuotas y admitir
fecha nula para el caso pagado completo. Desplegar backend y frontend compatibles;
no eliminar los nuevos campos ni volver al antiguo límite de cuotas si ya existen
conversiones pagadas completas. No se incluye deshacer conversión ni editar pagos.

Verificación de conversión:172 tests backend aprobados en PostgreSQL, incluidos
13 casos nuevos de conversión y concurrencia. Se cubre el caso simulado de esquema
histórico con categoría nula sin afirmar que exista en todas las instalaciones.
El bloqueo de familia usa `FOR NO KEY UPDATE`: serializa claves de conversión sin
bloquear la comprobación de clave foránea de una edición concurrente que crea un
mes nuevo. La regresión reproduce esa carrera y comprueba rechazo por instantánea
obsoleta, sin interbloqueo. Un ensayo independiente sobre datos sintéticos aprobó
94 comprobaciones con reversión completa. Despliegue y prueba real en navegador
pendientes de la validación del agente principal.
