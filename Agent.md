# Agent.md

## Overview

This repository is a Django 4.2 + Django REST Framework backend for a family budgeting application.
The API is mounted under `/api/` and uses session authentication.

Core business concepts:

- `Family`: tenant boundary.
- `Profile`: links `User` to a `Family` and stores a `role`.
- `Month`: monthly ledger per family, with `is_closed` to block edits.
- `Category`: family-owned classification for income and expenses.
- `Expense`: actual outgoing movement.
- `RecurringPayment`: fixed recurring expense definition.
- `PlannedExpense`: legacy monthly planned expense.
- `PlannedExpensePlan` + `PlannedExpenseVersion`: newer planned-expense system with history.
- `Income`: actual incoming movement.
- `IncomePlan` + `IncomePlanVersion`: planned/recurrent income system with history.

## Stack

- Python
- Django 4.2
- Django REST Framework
- PostgreSQL
- `python-dotenv` for local env vars

Main settings live in [config/settings.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/config/settings.py).

## Routing

Base URL config:

- [config/urls.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/config/urls.py)
- [core/urls.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/urls.py)

Main endpoints:

- `GET /api/budget/?year=YYYY&month=MM`
- `POST /api/recurring/generate/`
- `GET/POST /api/incomes/`
- `GET/PUT/PATCH/DELETE /api/incomes/{id}/`
- `GET/POST/PUT/PATCH/DELETE /api/expenses/`
- `GET/POST/PUT/PATCH/DELETE /api/categories/`
- `GET/POST/PUT/PATCH/DELETE /api/recurring-payments/`
- `GET /api/recurring-payments/{id}/payments/`
- `GET/POST/PUT/PATCH/DELETE /api/planned-expenses/`
- `GET/POST/PUT/PATCH/DELETE /api/planned-expense-plans/`
- `GET/POST/PUT/PATCH/DELETE /api/income-plans/`
- `GET/POST/PUT/PATCH/DELETE /api/income-plan-versions/`
- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `GET /api/csrf/`

Custom actions:

- `POST /api/planned-expense-plans/{id}/deactivate/`
- `POST /api/planned-expense-plans/{id}/reactivate/`
- `GET /api/income-plans/month/?year=YYYY&month=MM`
- `POST /api/income-plans/{id}/confirm/`
- `POST /api/income-plans/{id}/adjust/`
- `POST /api/income-plans/{id}/deactivate/`
- `POST /api/income-plans/{id}/reactivate/`
- `POST /api/recurring-payments/{id}/reactivate/`
- `GET /api/recurring-payments/{id}/payments/`

## Current API Notes

### Tenant model

The effective tenant boundary is `request.user.profile.family`.
Most current views correctly scope reads and writes through `Profile`.

### Auth model

- Session auth is the default DRF authentication class.
- Registration creates a new user, a dedicated family, and promotes the creator to `profile.role = "admin"`.
- `Profile.role` exists, but today it is descriptive rather than enforced.

### Closed months

`Month.is_closed` is a central business rule:

- closed months should not accept create/update/delete operations
- recurring generation and income plan resolution should respect closed months
- budget endpoints lazily create the `Month` row if it does not exist

### Planning systems

There are two expense-planning systems in parallel:

1. Legacy: `PlannedExpense`
2. Newer: `PlannedExpensePlan` + `PlannedExpenseVersion`

Budget aggregation currently combines both systems in the same response.

### Budget contract

`GET /api/budget/` returns:

- month metadata (`month_id`, `year`, `month`)
- top-level totals (`total_planned`, `total_spent`, `unplanned_total`, `remaining_amount`, `percentage_used`, `status`)
- `recurring`
- `planned`
- `income_plan_month`

`planned` and `recurring` now expose consistent category fields:

- `category`: numeric category id
- `category_name`
- `category_detail`

### Recurring payment detail contract

`GET /api/recurring-payments/{id}/payments/` returns the recurring payment itself plus a `payments` array with all associated `Expense` rows linked by `Expense.recurring_payment`.
This is the intended backend contract for the frontend "detalle rapido del gasto" use case and avoids client-side joins across separate endpoints.

### Seed commands

Available local seeds:

- [core/management/commands/seed_users.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/management/commands/seed_users.py)
- [core/management/commands/seed_categories.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/management/commands/seed_categories.py)

Seed payloads:

- [core/seeds/users.json](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/seeds/users.json)
- [core/seeds/categories.json](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/seeds/categories.json)

Typical local usage:

- `./venv/bin/python manage.py seed_users`
- `./venv/bin/python manage.py seed_categories`

## Important Files

- [core/models.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/models.py)
- [core/views/auth_view.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/auth_view.py)
- [core/views/budget_view.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/budget_view.py)
- [core/services/budget_service.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/services/budget_service.py)
- [core/views/income_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/income_viewset.py)
- [core/views/planned_income_plan_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_income_plan_viewset.py)
- [core/views/plannedIncome_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/plannedIncome_viewset.py)
- [core/views/planned_expense_plan_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_expense_plan_viewset.py)
- [core/serializers/planned_expense_plan_serializer.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/planned_expense_plan_serializer.py)
- [core/tests.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/tests.py)

## Audit Snapshot

Audit refreshed on April 14, 2026 against the current workspace.

### 1. High: plaintext credentials are stored in the repository

The repository currently contains credential material in tracked local files and seed data.
That is an operational security problem even for development because it normalizes password reuse and makes accidental exposure much easier.

Relevant files:

- [core/seeds/users.json](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/seeds/users.json)
- [.env](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/.env)

### 2. High: budget totals can still double-count spend when `PlannedExpensePlan` is involved

`get_planned_plans_summary()` measures spend by category for ongoing plans, but `Expense` has no foreign key to `PlannedExpensePlan`.
Because of that, the same expense can appear inside a planned-plan summary and also remain inside `unplanned_total`, which inflates `total_spent`.

Relevant code:

- [core/services/budget_service.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/services/budget_service.py)

### 3. High: plan updates can create overlapping versions

Both plan systems can auto-create a new version on update when `planned_amount` changes, but they do not close the previous version range before creating the new one.
That conflicts with the stricter overlap rules already enforced in the explicit version CRUD for income plans and makes version history ambiguous.

Relevant code:

- [core/views/planned_income_plan_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_income_plan_viewset.py)
- [core/views/planned_expense_plan_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_expense_plan_viewset.py)
- [core/views/plannedIncome_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/plannedIncome_viewset.py)

### 4. Medium: `Profile.role` is not enforced anywhere

The system models `admin` vs `member`, but no authorization layer uses that distinction.
In practice, any authenticated family member can mutate categories, recurring payments, plans, and budget-affecting resources.

Relevant code:

- [core/models.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/models.py)
- [core/views/auth_view.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/auth_view.py)
- [core/urls.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/urls.py)

### 5. Medium: test coverage exists now, but it is still narrow

The current tests cover multi-tenant boundaries, budget category payload shape, and recurring payment detail retrieval.
They do not yet cover closed-month enforcement across all endpoints, plan-version overlap behavior, seed commands, auth session flow, or recurring generation.

Relevant file:

- [core/tests.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/tests.py)

### 6. Low: there is dead duplicate budget view code under serializers

[core/serializers/budget_serializer.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/budget_serializer.py) contains an unused `BudgetView`.
Routing uses [core/views/budget_view.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/budget_view.py), so the serializer file is misleading and should either be deleted or renamed.

## Operational Notes

- Use the project virtualenv when running management commands:
  - `./venv/bin/python manage.py ...`
- `README.md` is still minimal, so this file and the code are the main source of truth.
- Session/CORS settings are environment-driven and safer than before, but there is still no dedicated `dev` vs `prod` settings split.
- Local verification in this workspace is easiest through the project virtualenv and lightweight checks such as `py_compile` when DB access is not available.

## Recommended Next Steps

1. Remove plaintext credentials from tracked files and rotate any reused passwords.
2. Decide how planned-plan spend should be linked so `budget.total_spent` cannot double-count category-based plan spend.
3. Unify version history rules across `IncomePlan` and `PlannedExpensePlan`, including explicit closure of previous ranges.
4. Enforce `Profile.role` with permissions for admin-only mutations.
5. Expand tests around closed months, version history, auth/session behavior, and seed commands.
6. Remove dead code such as the duplicate budget view under serializers and keep docs aligned with the routed implementation.
