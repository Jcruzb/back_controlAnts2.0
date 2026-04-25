# Quien paga - contrato frontend

## Selector de pagador

Usar:

```http
GET /api/family/members/
```

Respuesta:

```json
[
  {
    "id": 2,
    "username": "jcruz",
    "first_name": "Juan",
    "last_name": "Cruz",
    "email": "j.cruzb@outlook.com",
    "display_name": "Juan Cruz",
    "role": "admin"
  }
]
```

El endpoint devuelve solo usuarios activos de la familia autenticada.

## Gastos

`/api/expenses/` acepta y devuelve:

```json
{
  "payer": 2,
  "payer_detail": {
    "id": 2,
    "username": "jcruz",
    "first_name": "Juan",
    "last_name": "Cruz",
    "email": "j.cruzb@outlook.com",
    "display_name": "Juan Cruz",
    "role": "admin"
  }
}
```

Notas:

- `payer` es opcional para no romper clientes existentes.
- Si se crea un gasto sin `payer`, el backend usa el usuario autenticado.
- `payer: null` esta permitido para datos antiguos o casos sin pagador definido.
- Si se envia un usuario que no pertenece a la familia, la API responde `400`.
- El listado permite filtrar por pagador con `GET /api/expenses/?payer=2`.

## Gastos fijos

`/api/recurring-payments/` tambien acepta y devuelve `payer` y `payer_detail`.

Si un gasto fijo tiene `payer`, los gastos generados por:

```http
POST /api/recurring/generate/
```

heredan ese pagador. Si no lo tiene, se usa el usuario autenticado.

## Presupuesto

`GET /api/budget/?year=YYYY&month=M` incluye `payer` y `payer_detail` en cada item de `recurring`.

Los totales existentes no cambian.
