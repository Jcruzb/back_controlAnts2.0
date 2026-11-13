# ControlAnts 2.0 Backend

Backend Django 4.2 y Django REST Framework para la gestión de presupuestos
familiares. La API usa autenticación de sesión, PostgreSQL y aislamiento de los
datos por familia.

Las reglas funcionales, contratos sensibles y riesgos conocidos se documentan
en [Agent.md](Agent.md). Las reglas de trabajo para agentes y tooling están en
[AGENTS.md](AGENTS.md).

## Integración de mejoras (13 de noviembre de 2026)

Para descargar y probar las ramas de ingresos, financiaciones y Nilo juntas,
seguir [la guía de integración local](docs/LOCAL_INTEGRATION_20261113.md). Incluye
Python 3.9, una base PostgreSQL aislada, configuración del asistente y los comandos
de pruebas.

## Preparación local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Configura en `.env` la conexión PostgreSQL y una `SECRET_KEY` local antes de
ejecutar migraciones. La API queda disponible bajo `/api/`.

## Datos de demostración

El escenario recomendado para pruebas manuales crea una familia aislada con
usuarios, categorías configurables, meses, ingresos, gastos, planes y pagos
recurrentes:

```bash
./venv/bin/python manage.py seed_all
```

Credenciales locales:

- `demo@controlants.local` / `ControlAntsDemo2026!`
- `blanca.demo@controlants.local` / `ControlAntsDemo2026!`

Estas credenciales y los importes del escenario proceden de los JSON ubicados
en `core/seeds/demo/`.

Consulta [Seed.md](Seed.md) para ejecutar cada dominio por separado, cambiar el rango de meses,
restablecer el escenario y conocer sus protecciones de entorno.

## Pruebas

```bash
./venv/bin/python manage.py test
./venv/bin/python manage.py test core.test_seed_demo
```

## Endpoints principales

- Autenticación y cuenta: `/api/auth/`
- Presupuesto mensual: `/api/budget/`
- Gastos e ingresos: `/api/expenses/`, `/api/incomes/`
- Categorías configurables: `/api/categories/`
- Pagos recurrentes: `/api/recurring-payments/`
- Planificación: `/api/planned-expense-plans/`, `/api/income-plans/`
- Miembros de la familia: `/api/family/members/`

Los contratos detallados, incluidos meses cerrados, pagadores y estados
mensuales de pagos recurrentes, se mantienen en [Agent.md](Agent.md).
