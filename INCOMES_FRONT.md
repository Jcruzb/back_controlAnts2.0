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
