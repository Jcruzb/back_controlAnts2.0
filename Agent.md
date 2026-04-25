# Agent.md

## Overview

This repository is a Django 4.2 + Django REST Framework backend for a family budgeting application.
The API is mounted under `/api/` and uses session authentication.

Core business concepts:

- `Family`: tenant boundary.
- `Profile`: links `User` to a `Family` and stores a `role`.
- `Month`: monthly ledger per family, with `is_closed` to block edits.
- `Category`: family-owned classification for income and expenses.
- `Expense`: actual outgoing movement. `user` is the creator/registrar; `payer` is the family user who paid or is paying.
- `RecurringPayment`: fixed recurring expense definition. It can also define a `payer` used by generated expenses.
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
- `GET /api/family/members/`
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

### Income plan adjustment contract

`IncomePlan` uses `IncomePlanVersion` ranges to decide the planned amount for a month.
For recurrent incomes such as salaries, `POST /api/income-plans/{id}/adjust/?year=YYYY&month=MM` means:

> change this recurrent income from the selected month forward.

Current behavior:

- `adjust` accepts `amount` and also tolerates `planned_amount` as an alias.
- `adjust` creates or updates an `IncomePlanVersion` starting in the selected month.
- The previously active version is closed on the month before the adjustment.
- Later pre-existing versions are preserved, so the new version ends the month before the next future version if one exists.
- `adjust` still creates the real `Income` for the selected month, preserving the existing frontend contract.
- `confirm` creates the real `Income` from the currently effective version and does not change version ranges.
- `GET /api/income-plans/month/?year=YYYY&month=MM` resolves the latest version whose `valid_from` is before or equal to the month and whose `valid_to` is empty or after/equal to the month.

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

`recurring` items also expose payer fields when available:

- `payer`: numeric user id or `null`
- `payer_detail`: family-member payload or `null`

### Payer contract

The backend supports "quien paga" without introducing a separate member model.
The payer is a `User` constrained by `Profile.family`.

Current contract:

- `GET /api/family/members/` returns active users in the authenticated user's family for payer selectors.
- `Expense.payer` is optional and accepts a family user id.
- Creating an expense without `payer` defaults it to the authenticated user.
- `GET /api/expenses/?payer={user_id}` filters expenses by payer.
- `RecurringPayment.payer` is optional and accepts a family user id.
- Generated recurring expenses inherit `RecurringPayment.payer`; if absent, they fall back to the authenticated user.
- Expense and recurring-payment serializers return both `payer` and `payer_detail`.

Frontend-specific notes live in [PAYER_FRONT.md](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/PAYER_FRONT.md).

### Recurring payment detail contract

`GET /api/recurring-payments/{id}/payments/` returns the recurring payment itself plus a `payments` array with all associated `Expense` rows linked by `Expense.recurring_payment`.
This is the intended backend contract for the frontend "detalle rapido del gasto" use case and avoids client-side joins across separate endpoints.

### Seed commands

Available local seeds:

- [core/management/commands/seed_users.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/management/commands/seed_users.py)
- [core/management/commands/seed_categories.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/management/commands/seed_categories.py)
- [core/management/commands/seed_recurring_payments.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/management/commands/seed_recurring_payments.py)

Seed payloads:

- [core/seeds/users.json](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/seeds/users.json)
- [core/seeds/categories.json](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/seeds/categories.json)
- [core/seeds/recurring_payments.json](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/seeds/recurring_payments.json)

Typical local usage:

- `./venv/bin/python manage.py seed_users`
- `./venv/bin/python manage.py seed_categories`
- `./venv/bin/python manage.py seed_recurring_payments`

Recurring-payment seed rows may include optional `payer` as a username. The command validates that the payer belongs to the same family.

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
- [core/serializers/family_member_serializer.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/family_member_serializer.py)
- [core/views/family_member_view.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/family_member_view.py)
- [core/tests.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/tests.py)

## Audit Snapshot

Audit refreshed on April 25, 2026 against the current workspace.

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

### 3. High: planned-expense plan updates can create overlapping versions

The income-plan `adjust` action now closes the previous `IncomePlanVersion` range before opening the new one.
However, the planned-expense plan update flow can still auto-create a new version when `planned_amount` changes without closing the previous version range.
That conflicts with the stricter overlap rules already enforced in explicit version CRUD and makes planned-expense version history ambiguous.

Relevant code:

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

The current tests cover multi-tenant boundaries, budget category payload shape, recurring payment detail retrieval, payer validation/defaulting/filtering, family-member listing, recurring generation payer inheritance, and forward income-plan adjustments.
They do not yet cover closed-month enforcement across all endpoints, plan-version overlap behavior, seed commands, or auth session flow.

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
3. Unify remaining planned-expense version history rules with the income-plan adjustment behavior, including explicit closure of previous ranges.
4. Enforce `Profile.role` with permissions for admin-only mutations.
5. Expand tests around closed months, version history, auth/session behavior, and seed commands.
6. Remove dead code such as the duplicate budget view under serializers and keep docs aligned with the routed implementation.
