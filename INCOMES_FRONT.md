# INCOMES_FRONT.md

Conecta el frontend al backend Django en `http://127.0.0.1:8000/api/` usando autenticacion por sesion con cookies y CSRF.

## Reglas Obligatorias

- Usa `credentials: 'include'` en todas las requests.
- Antes de cualquier `POST`, llama a `GET /api/csrf/`.
- En cada `POST`, envia `X-CSRFToken` con el valor de la cookie `csrftoken`.
- No uses JWT ni `localStorage` para credenciales.

## Objetivo

Implementa la UI completa de ingresos usando el contrato actual del backend, sin asumir endpoints que no existen.

## Endpoints Reales

### 1. `GET /api/incomes/?year=YYYY&month=MM`

Lista ingresos del mes de la familia autenticada.
Si no mandas `year` y `month`, devuelve todos los ingresos de la familia.

Ejemplo de item:

```json
{
  "id": 12,
  "amount": "1250.00",
  "category": 3,
  "category_detail": {
    "id": 3,
    "name": "Salario",
    "icon": "wallet",
    "color": "#22c55e",
    "description": ""
  },
  "income_plan": 5,
  "month": 9,
  "user": 1,
  "date": "2026-04-30",
  "description": "Nomina abril",
  "created_at": "2026-04-05T10:00:00Z"
}
```

### 2. `POST /api/incomes/`

Crea ingreso manual o resuelve manualmente uno ligado a plan.

Body minimo manual:

```json
{
  "amount": "1250.00",
  "category": 3,
  "date": "2026-04-30",
  "description": "Nomina abril"
}
```

Body con plan:

```json
{
  "amount": "1250.00",
  "category": 3,
  "income_plan": 5,
  "date": "2026-04-30",
  "description": "Nomina abril"
}
```

Reglas:

- `amount` debe ser mayor que 0.
- `date` es obligatoria.
- `category` debe pertenecer a la familia del usuario.
- Si mandas `income_plan`, la categoria debe coincidir con la del plan.
- No puede existir otro ingreso del mismo `income_plan` en el mismo mes.
- Si el mes esta cerrado, el backend rechaza la operacion.

### 3. `GET /api/income-plans/`

Lista planes de ingreso de la familia autenticada.

### 4. `POST /api/income-plans/`

Crea la definicion de ingreso planificado.

Body:

```json
{
  "category": 3,
  "name": "Salario principal",
  "plan_type": "ONGOING",
  "due_day": 30,
  "active": true,
  "start_month": 10,
  "end_month": null
}
```

`plan_type` puede ser `ONE_MONTH` o `ONGOING`.

### 5. `GET /api/income-plans/month/?year=2026&month=4`

Devuelve estado mensual de planes aplicables.

Respuesta:

```json
{
  "month": {
    "year": 2026,
    "month": 4,
    "is_closed": false
  },
  "results": [
    {
      "plan_id": 5,
      "name": "Salario principal",
      "plan_type": "ONGOING",
      "due_day": 30,
      "category": 3,
      "category_detail": {
        "id": 3,
        "name": "Salario",
        "icon": "wallet",
        "color": "#22c55e",
        "description": ""
      },
      "version_id": 8,
      "planned_amount": "1250.00",
      "status": "PENDING",
      "can_resolve": true,
      "resolved_income": null
    }
  ]
}
```

Estados posibles:

- `PENDING`
- `RESOLVED`
- `MISSING_VERSION`

### 6. `POST /api/income-plans/{id}/confirm/`

Crea el ingreso usando el importe planificado.

Body:

```json
{
  "year": 2026,
  "month": 4,
  "description": "Nomina abril"
}
```

Respuesta:

```json
{
  "detail": "OK",
  "income_id": 12
}
```

### 7. `POST /api/income-plans/{id}/adjust/`

Crea el ingreso ajustando importe y opcionalmente fecha.

Body:

```json
{
  "year": 2026,
  "month": 4,
  "amount": "1325.50",
  "date": "2026-04-29",
  "description": "Nomina abril ajustada"
}
```

Respuesta:

```json
{
  "detail": "OK",
  "income_id": 13
}
```

### 8. `GET /api/income-plan-versions/`

### 9. `POST /api/income-plan-versions/`

Sirve para definir importes por rango de meses.

Body:

```json
{
  "plan": 5,
  "planned_amount": "1250.00",
  "valid_from": 10,
  "valid_to": null
}
```

## Limitaciones Actuales Del Backend

- No implementes edicion ni borrado de `incomes` manuales desde UI porque ahora mismo el backend no expone `/api/incomes/{id}/`.
- Si el backend devuelve errores de validacion, pinta literalmente `detail` o el error de campo que llegue.

## UI Esperada

La pantalla de ingresos debe tener:

- Filtro por `year` y `month`
- Listado de ingresos del mes
- Formulario de ingreso manual
- Bloque de ingresos planificados pendientes usando `/income-plans/month/`
- Acciones `Confirmar` y `Ajustar` para planes pendientes
- Estado visual para `RESOLVED` y `MISSING_VERSION`

## Cobro independiente de la previsión (noviembre de 2026)

Los endpoints anteriores `confirm` y `adjust` mantienen sus contratos. El nuevo
frontend debe utilizar estas operaciones separadas:

- `POST /api/income-plans/{id}/record-receipt/?year=2026&month=8`
  con `{"amount":"950.00","date":"2026-08-28","description":"Nómina"}`.
  `amount` y `date` son obligatorios; la fecha pertenece al mes seleccionado.
  Registra un único ingreso real sin modificar ninguna versión prevista.
  Responde 200 con `{"detail":"OK","income_id":123,"created":true}`.
  Repetir los mismos valores normalizados devuelve el mismo id y `created:false`.
  Repetir con valores distintos devuelve 409 y el `income_id` existente; no lo
  sobrescribe. Refrescar ingresos, planes y resumen después de guardar o de un 409.
  Administradores y miembros de la familia pueden registrar cobros.
- `POST /api/income-plans/{id}/change-planned-amount/?year=2026&month=9`
  con `{"amount":"1200.00"}`. Solo administradores. Cambia el importe previsto
  desde septiembre, conservando las versiones futuras que ya existían. No crea
  ni modifica ingresos reales, incluso si el mes ya tiene un cobro.
  Responde 200 con `detail`, `version_id`, `planned_amount` y
  `effective_month: {year, month}`.

Ambas operaciones requieren sesión y CSRF; rechazan planes de otra familia,
planes inactivos y meses cerrados. Los importes admiten dos decimales y deben ser
positivos. El cambio de previsión conserva el bloqueo existente cuando hay meses
cerrados posteriores. Crear un plan nunca registra un cobro y rechaza períodos
que incluyan meses cerrados. No hay migraciones nuevas.

Pruebas de contrato, permisos, repetición, concurrencia y compatibilidad:

```sh
./venv/bin/python manage.py test core.test_income_receipts core.tests.IncomePlanAdjustmentTests --noinput
./venv/bin/python manage.py test --noinput
```

Usar una base PostgreSQL local de pruebas y un usuario con permiso para crear la
base temporal `test_<DB_NAME>`. La prueba de concurrencia usa dos conexiones reales
PostgreSQL; se omite explícitamente en otros motores.
