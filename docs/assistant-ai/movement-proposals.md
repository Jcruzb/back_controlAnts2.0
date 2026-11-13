# Registro múltiple de Nilo con confirmación

Estos endpoints son adicionales a `assistant/messages/`, cuyo contrato de consulta
no cambia. Requieren sesión, CSRF y `ASSISTANT_ENABLED=true`. No llaman a ningún
proveedor externo, no deducen una familia desde el texto y no admiten enlaces a
planes, cuotas ni pagos recurrentes: registran movimientos puntuales.

## 1. Borrador editable

`POST /api/assistant/movement-drafts/`

```json
{"text":"Gasté 12,50 en alimentación; Cobré 1000 de sueldo 2026-08-16","year":2026,"month":8}
```

Devuelve 200 `{rows, source:"deterministic", requires_confirmation:true}`.
Cada fila contiene `kind` (`expense` o `income`), `amount`, `date`, `category`,
`description`, `alias`, `learn_alias` y `errors`. Los campos ambiguos son `null`;
la interfaz debe pedir su revisión. Un movimiento por línea o punto y coma,
máximo 20, texto máximo 4000 caracteres. Admite números con coma o punto decimal
y fechas ISO. Sin fecha explícita propone hoy si coincide con el período elegido,
o el primer día de ese período. Referencias como «ayer» requieren fecha manual.

Las categorías se buscan por nombre normalizado y por alias aprendidos dentro de
la familia. Varias coincidencias no se resuelven por prioridad: se pide selección.
La redacción ambigua no genera una operación automática. Esta fase no crea meses,
propuestas, ingresos ni gastos.

## 2. Preparar los movimientos revisados

`POST /api/assistant/movement-proposals/`

```json
{"movements":[{"kind":"expense","amount":"12.50","date":"2026-08-15","category":4,"description":"Compra","alias":"mercado","learn_alias":true}]}
```

Omitir `errors` del borrador. Campos desconocidos se rechazan. `description`,
`alias` y `learn_alias` son opcionales. La categoría debe existir en la familia;
importe positivo, máximo ocho dígitos enteros y dos decimales; fecha válida en un
mes abierto. No se crean movimientos todavía. Devuelve 201
`{id, expires_at, movements, requires_confirmation:true}`. El identificador UUID
pertenece al actor y familia autenticados y caduca a los 15 minutos.

Mostrar los datos devueltos íntegros antes de ofrecer el botón final. Para editar,
preparar otra propuesta; el contenido de una propuesta guardada es inmutable.

## 3. Confirmar explícitamente

`POST /api/assistant/movement-proposals/{id}/confirm/`

```json
{"confirmed":true}
```

Solo se acepta ese objeto y el booleano literal `true`. Se revalidan categoría,
familia y meses abiertos. El lote completo se registra en una transacción o no se
registra ninguna fila. Los escritores reutilizan validaciones y valores por
defecto de los endpoints ordinarios de ingresos y gastos. Devuelve 200
`{id, created:true, movements:[{kind,id}]}`.

Reintentar o confirmar simultáneamente el mismo UUID devuelve los mismos ids,
con `created:false` para reintentos. Un UUID de otro usuario, incluso de la misma
familia, devuelve 404. Una propuesta caducada devuelve 409; las validaciones
fallidas devuelven 400. Refrescar presupuesto y listados tras el éxito.

## Aprender alias

Solo se guarda el alias de una fila con `learn_alias:true`, una categoría elegida
y confirmación final exitosa. La normalización ignora acentos, puntuación y
mayúsculas. Un alias ya asociado a otra categoría se rechaza, nunca se sobrescribe
silenciosamente. Se comparte dentro de la familia y nunca entre familias. Una
propuesta fallida o sin confirmar no aprende nada.

## Pruebas y migración

Aplicar `0019_nilo_proposals` (depende de `0017_plannedexpenseoccurrence`). Crea
únicamente tablas nuevas; no migra movimientos existentes.

```sh
./venv/bin/python manage.py migrate
./venv/bin/python manage.py test core.test_assistant_movements --noinput
./venv/bin/python manage.py test --noinput
```

Las pruebas incluyen CSRF, aislamiento, importes ambiguos, expiración,
revalidación, rollback de lote, alias opt-in y confirmación simultánea con
PostgreSQL. El reconocimiento de voz pertenece al navegador: el backend recibe
el texto transcrito y exige la misma revisión/confirmación que para texto escrito.
