# Seeds para desarrollo local

Los seeds crean un escenario completo y aislado en `Familia Demo ControlAnts`.
Son idempotentes: se pueden ejecutar varias veces sin duplicar movimientos.

## Ejecutar todos

```bash
./venv/bin/python manage.py seed_all
```

También se puede elegir la cantidad de meses o limpiar únicamente el escenario demo:

```bash
./venv/bin/python manage.py seed_all --months 6
./venv/bin/python manage.py seed_all --reset
```

El equivalente directo es `./venv/bin/python manage.py seed_demo`.

## Ejecutar por dominio

Cada comando incluye automáticamente las dependencias necesarias. Por ejemplo,
gastos necesita antes usuarios, categorías, meses, planificación y pagos fijos.

```bash
# Credenciales, usuarios, perfiles y familia
./venv/bin/python manage.py seed_demo --only users

# Usuarios y categorías configurables
./venv/bin/python manage.py seed_demo --only categories

# Usuarios, categorías, meses, planes de sueldo e ingresos reales
./venv/bin/python manage.py seed_demo --only incomes

# Presupuestos mensuales y plan futuro (más sus dependencias)
./venv/bin/python manage.py seed_demo --only planned_expenses

# Gastos fijos/pagos recurrentes (más sus dependencias)
./venv/bin/python manage.py seed_demo --only recurring_payments

# Gastos variables, pagos de gastos fijos y estados mensuales (escenario completo)
./venv/bin/python manage.py seed_demo --only expenses
```

Todos aceptan `--months N` (entre 1 y 60).

## Datos que entran a la base

Los valores se editan y auditan en JSON, sin sueldos, importes ni credenciales
ocultos en el comando Python:

- `core/seeds/demo/users.json`: familia, prefijo, usuarios y contraseñas.
- `core/seeds/demo/categories.json`: categorías, iconos, colores y descripciones.
- `core/seeds/demo/incomes.json`: sueldos recurrentes e ingresos puntuales.
- `core/seeds/demo/planned_expenses.json`: presupuestos mensuales y futuro.
- `core/seeds/demo/recurring_payments.json`: gastos fijos, pagador e importe.
- `core/seeds/demo/expenses.json`: gastos variables y pagos de gastos fijos.

Credenciales actuales (fuente: `core/seeds/demo/users.json`):

- `demo@controlants.local` / `ControlAntsDemo2026!`
- `blanca.demo@controlants.local` / `ControlAntsDemo2026!`

## Seguridad

Con `DEBUG=False` los comandos abortan. Para una ejecución deliberada fuera de
debug debe definirse `ALLOW_DEMO_SEEDS=true`. `--reset` solo elimina la familia y
los usuarios reservados del demo, y aborta si detecta miembros ajenos.

## Seeds históricos

Se conservan para compatibilidad los comandos `seed_users`, `seed_categories` y
`seed_recurring_payments`, que leen los JSON ubicados directamente en
`core/seeds/`. No forman el escenario demo completo; para probar toda la app use
`seed_all`.
