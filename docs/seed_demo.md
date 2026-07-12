# Datos de demostración

La guía de ejecución actual, incluidos los comandos independientes y la lista
de JSON, está en [`Seed.md`](../Seed.md).

El backend conserva los comandos JSON históricos (`seed_users`, `seed_categories`
y `seed_recurring_payments`). Para una prueba manual completa debe usarse
`seed_all`, que delega en el escenario aislado e idempotente:

```bash
./venv/bin/python manage.py seed_all
./venv/bin/python manage.py seed_demo --months 6
./venv/bin/python manage.py seed_demo --reset
```

`--months` incluye el mes actual, un mes futuro cuando el valor es mayor que uno
y usa el resto como histórico. El valor por defecto es 4 (dos anteriores, actual
y siguiente).

Credenciales locales:

- `demo@controlants.local` / `ControlAntsDemo2026!`
- `blanca.demo@controlants.local` / `ControlAntsDemo2026!`

Estas credenciales y todos los importes del escenario están declarados en los
archivos de `core/seeds/demo/`. El archivo `core/seeds/users.json` pertenece al
comando histórico `seed_users` y contiene un conjunto de usuarios diferente.

El comando usa `set_password`, una transacción y claves naturales estables. Puede
ejecutarse repetidamente sin duplicar sus movimientos. Todos los nombres internos
del escenario usan el prefijo `[DEMO]` y viven dentro de `Familia Demo ControlAnts`.
`--reset` valida que esa familia no contenga miembros ajenos antes de eliminarla y
no toca otras familias o usuarios.

## Protección de entorno

La ejecución está permitida con `DEBUG=True`. Con `DEBUG=False` aborta, salvo que
el operador habilite conscientemente `ALLOW_DEMO_SEEDS=true`. No se ejecuta durante
el arranque de Django.

## Cobertura y límite del modelo

El escenario crea usuarios y perfiles, familia, meses, categorías configurables,
planes y versiones de ingresos, ingresos reales, planificación variable legacy
vinculada a gastos, un plan/version moderno de un mes futuro, pagos recurrentes,
ocurrencias y gastos reales. Incluye pagos parciales, exactos, completados y por
encima del importe, además de gastos planificados y no planificados.

`RecurringPayment` no tiene un campo de frecuencia: actualmente representa pagos
mensuales activos entre `start_date` y `end_date`. Por ello el seed no simula
frecuencias trimestrales o anuales que el contrato del backend no soporta.
