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
- `GET/PATCH /api/recurring-payments/{id}/month-status/?year=YYYY&month=MM`
- `GET/PATCH /api/planned-expenses/{id}/month-status/?year=YYYY&month=MM`
- `GET/PATCH /api/planned-expense-plans/{id}/month-status/?year=YYYY&month=MM`
- `GET /api/family/members/`
- `GET/POST/PUT/PATCH/DELETE /api/planned-expenses/`
- `GET/POST/PUT/PATCH/DELETE /api/planned-expense-plans/`
- `GET/POST/PUT/PATCH/DELETE /api/income-plans/`
- `GET/POST/PUT/PATCH/DELETE /api/income-plan-versions/`
- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `PATCH /api/auth/me/`
- `POST /api/auth/change-password/`
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
- `Profile.role` is enforced for configuration mutations. Members retain read
  access and operational actions such as recording movements, confirming an
  income, and completing/reopening a recurring month.

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
- top-level totals (`total_planned`, `total_spent`, `actual_spent`, `unplanned_total`, `remaining_amount`, `percentage_used`, `status`)
- `recurring`
- `planned`
- `income_plan_month`

Top-level budget semantics:

- `total_planned`: all recurring and planned obligations for the selected month.
- `total_spent`: all real expense movements registered in the month, whether
  planned, recurring or unplanned.
- `actual_spent`: explicit, backwards-compatible alias of `total_spent` for UI
  labels such as "Gasto real".
- `unplanned_total`: subset of real spending that has no planned or recurring
  linkage; it must not be added to `total_spent` again.
- `remaining_amount` / `difference_amount`: signed budget variance,
  `total_planned - total_spent`.
- `budget_variance`: explicit compatible alias of that variance.
- `planned_paid_amount`: real movements linked to recurring or planned obligations.
- `planned_pending_amount`: canonical remaining obligation across recurring and planned rows.
- `actual_income`: real `Income` movements registered for the family month.
- `cash_balance`: real monthly cash balance, `actual_income - total_spent`.
- `status`: `over` only when real spending is strictly greater than the budget;
  exact coverage is `ok`, and spending without any configured budget is `over`.

`remaining_amount` is not cash available. Assistant-facing contracts must call it
budget variance and use `cash_balance` when answering how much real money remains.

Versioned `ONE_MONTH` planned-expense plans apply only to their configured month.
Migration-created mirrors of legacy planned expenses are deduplicated so the
legacy row remains the historical source of truth.

### Experimental assistant contract

`POST /api/assistant/messages/` is disabled by default, session-authenticated,
CSRF-protected and supports the dependency-free mock plus an optional OpenAI
router configured only in the backend environment. It derives
the tenant from `request.user.profile.family`, exposes six statically registered
read tools and rejects caller-supplied tenant identifiers. Assistant budget/status
tools use `BudgetService(materialize=False)` so they do not create Month or
occurrence rows. See `docs/assistant-ai/` for the complete contract.

Known Spanish monthly questions are routed before the provider through a
deterministic engine. Successful matches return visual schema `1.0`, source
`deterministic`, a registered intent, an optional configured-timezone period,
and up to ten validated blocks. The nine allowed block types and twelve intents
are static registries. Deterministic responses cannot contain recommendation or
question blocks and initially expose at most two objective alerts. Detail actions
post only an allowlisted intent plus year/month back to the same endpoint.

The verified frontend navigation allowlist is `/`, `/dashboard`, `/expenses`,
`/incomes`, `/recurring`, `/categories`, and `/account`. External URLs, danger
actions, caller-supplied visual blocks, tenant identifiers, and write intents are
rejected. Unmatched requests use the configured provider. The OpenAI provider
receives only the question and selected/default period, chooses one allowlisted
read intent through Responses API function calling, and never receives tenant
ids or raw financial DTOs. ControlAnts then queries the database and renders the
visual response deterministically. The browser never receives the provider token.

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

### Planned expense plan linkage

Expenses may link to the legacy `planned_expense` or the newer
`planned_expense_plan`, but never to more than one planned/recurring source.
New-plan budget spend is aggregated only through `planned_expense_plan`, avoiding
category-based double counting. Budget plan rows expose numeric `plan_id` while
retaining the existing prefixed display `id`.

Changing a planned plan amount requires `effective_month` (a family month id).
The previous version is closed on the preceding month and future versions are
preserved without overlap.

Frontend-specific notes live in [PAYER_FRONT.md](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/PAYER_FRONT.md).

### Recurring payment detail contract

`GET /api/recurring-payments/{id}/payments/` returns the recurring payment itself plus a `payments` array with all associated `Expense` rows linked by `Expense.recurring_payment`.
This is the intended backend contract for the frontend "detalle rapido del gasto" use case and avoids client-side joins across separate endpoints.

### Recurring payment monthly status contract

`RecurringPaymentOccurrence` stores whether one recurring obligation has been
explicitly completed for a specific family month. Real money movements remain
represented by `Expense` rows linked through `Expense.recurring_payment`.

- `GET /api/recurring-payments/{id}/month-status/?year=YYYY&month=MM` returns
  `planned_amount`, `paid_amount`, `pending_amount`, signed `difference_amount`,
  `is_completed` and `payment_status`.
- `PATCH` on the same endpoint accepts `{"is_completed": true|false}`.
- Possible payment states are `pending`, `partially_paid`, `covered`,
  `exceeded` and `completed`.
- Completing an occurrence forces its pending amount to zero but does not
  create or alter an `Expense`.
- Completed occurrences reject movement changes and are skipped by recurring
  expense generation until reopened.
- Closed months reject status changes.
- Budget recurring rows expose the same canonical amounts and payment status,
  plus top-level `recurring_pending_amount` and `total_pending_amount`.

### Planned payment monthly status contract

Legacy `PlannedExpense` rows and versioned `PlannedExpensePlan` rows use the
same explicit monthly completion semantics as recurring payments.

- Their dedicated `month-status` endpoints accept `PATCH {"is_completed": true|false}`.
- Budget `planned` rows expose `paid_amount`, `pending_amount`,
  `difference_amount`, `is_completed` and `payment_status`.
- Completing a planned occurrence makes its monthly pending amount zero without
  changing the planned definition, its version history, or any real `Expense`.
- Completion is allowed with zero, partial, exact or excess payments.
- Completed occurrences reject movement changes until reopened, and closed
  family months reject completion changes.
- `Expense` responses expose `planned_payment_month` when linked to either
  planned-expense system.

### Seed commands

Preferred complete demo scenario:

- [core/management/commands/seed_demo.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/management/commands/seed_demo.py)
- Run all: `./venv/bin/python manage.py seed_all`
- Custom range: `./venv/bin/python manage.py seed_demo --months 6`
- Safe cleanup: `./venv/bin/python manage.py seed_demo --reset`
- Full documentation: [Seed.md](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/Seed.md)

The command is idempotent, transactional, isolated in `Familia Demo ControlAnts`,
and blocked when `DEBUG=False` unless `ALLOW_DEMO_SEEDS=true` is explicitly set.

Demo login credentials are intentionally local and fixed:

- `demo@controlants.local` / `ControlAntsDemo2026!`
- `blanca.demo@controlants.local` / `ControlAntsDemo2026!`

These credentials and all demo business values are loaded from JSON files under
`core/seeds/demo/`. The historical `seed_users` command still loads its separate
users and passwords from `core/seeds/users.json`.

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

Audit remediated on July 12, 2026. The current implementation now has explicit
plan linkage, chronological month queries, non-overlapping planned versions,
admin-only configuration mutations, authentication throttling, pagination and
database constraints for core numeric/range invariants. Historical local seed
identities are fictitious.

### Remaining test scope

The current tests cover multi-tenant boundaries, budget category payload shape,
recurring payment detail and monthly status, payer validation/defaulting/filtering,
family-member listing, recurring generation payer inheritance, forward income-plan
adjustments, auth profile/password operations, and the isolated demo seed's
idempotency, reset isolation and production guard.
Additional regression coverage verifies chronological month ordering, explicit
plan spend allocation, planned version closure, role permissions and invalid
budget months. Closed-month enforcement across every endpoint remains a useful
future expansion.

Relevant file:

- [core/tests.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/tests.py)
- [core/test_seed_demo.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/test_seed_demo.py)

## Operational Notes

- Use the project virtualenv when running management commands:
  - `./venv/bin/python manage.py ...`
- `README.md` provides setup and local demo guidance; this file documents the
  sensitive functional contracts and known risks in greater depth.
- Session/CORS settings are environment-driven and safer than before, but there is still no dedicated `dev` vs `prod` settings split.
- Local verification in this workspace is easiest through the project virtualenv and lightweight checks such as `py_compile` when DB access is not available.

## Recommended Next Steps

1. Expand tests around closed months across every mutation endpoint.
2. Consider a dedicated production settings module as deployment complexity grows.
3. Add observability for throttled authentication attempts and permission denials.
