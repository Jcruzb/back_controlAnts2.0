# Agent.md

## Overview

This repository is a Django 4.2 + Django REST Framework backend for a family budgeting application.
The API is mounted under `/api/` and uses session authentication.

Core business concepts:

- `Family`: tenant boundary.
- `Profile`: links `User` to a `Family` and role.
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

- `GET/POST /api/incomes/`
- `GET /api/budget/?year=YYYY&month=MM`
- `POST /api/recurring/generate/`
- `GET/POST/PUT/DELETE /api/expenses/`
- `GET/POST/PUT/DELETE /api/categories/`
- `GET/POST/PUT/DELETE /api/recurring-payments/`
- `GET/POST/PUT/DELETE /api/planned-expenses/`
- `GET/POST/PUT/DELETE /api/planned-expense-plans/`
- `GET/POST/PUT/DELETE /api/income-plans/`
- `GET/POST/PUT/DELETE /api/income-plan-versions/`

Custom actions:

- `POST /api/planned-expense-plans/{id}/deactivate/`
- `POST /api/planned-expense-plans/{id}/reactivate/`
- `GET /api/income-plans/month/?year=YYYY&month=MM`
- `POST /api/income-plans/{id}/confirm/`
- `POST /api/income-plans/{id}/adjust/`
- `POST /api/recurring-payments/{id}/reactivate/`

## Domain Notes

### Tenant model

Most views correctly scope data through `request.user.profile.family`.
That is the effective multi-tenant boundary in this codebase.

### Closed months

`Month.is_closed` is a central business rule:

- closed months should not accept create/update/delete operations
- income plan resolution also respects closed months
- budget endpoints create the `Month` row lazily if it does not exist

### Planning systems

There are two expense-planning systems in parallel:

1. Legacy: `PlannedExpense`
2. Newer: `PlannedExpensePlan` + `PlannedExpenseVersion`

Budget aggregation currently combines both systems.

### Income workflow

The income plan flow is more mature than the planned-expense-plan flow:

- `IncomePlan` defines applicability window and category
- `IncomePlanVersion` defines amount over a month range
- `/income-plans/month/` returns month status (`PENDING`, `RESOLVED`, `MISSING_VERSION`)
- `/confirm/` and `/adjust/` materialize an `Income` row for the selected month

## Important Files

- [core/models.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/models.py)
- [core/views/budget_view.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/budget_view.py)
- [core/services/budget_service.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/services/budget_service.py)
- [core/views/income_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/income_viewset.py)
- [core/views/planned_income_plan_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_income_plan_viewset.py)
- [core/views/plannedIncome_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/plannedIncome_viewset.py)
- [core/views/planned_expense_plan_viewset.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_expense_plan_viewset.py)
- [core/serializers/planned_expense_plan_serializer.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/planned_expense_plan_serializer.py)

## Risks Found During Review

### 1. `PlannedExpensePlan` uses `user.family` instead of `user.profile.family`

The new planned-expense serializer assumes a direct `family` attribute on `User`, but the rest of the codebase uses `Profile`.
This likely breaks creation/validation for planned expense plans unless `User` has been extended elsewhere.

Relevant code:

- [core/serializers/planned_expense_plan_serializer.py:43](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/planned_expense_plan_serializer.py#L43)
- [core/serializers/planned_expense_plan_serializer.py:88](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/planned_expense_plan_serializer.py#L88)
- [core/serializers/planned_expense_plan_serializer.py:121](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/planned_expense_plan_serializer.py#L121)

### 2. Budget totals can double-count expenses covered by `PlannedExpensePlan`

`get_planned_plans_summary()` counts spend by category for ongoing plans, but `get_unplanned_expenses_total()` still includes those same expenses because `Expense` has no link to `PlannedExpensePlan`.
That means `total_spent` can count the same expense once inside planned summaries and again inside `unplanned_total`.

Relevant code:

- [core/services/budget_service.py:97](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/services/budget_service.py#L97)
- [core/services/budget_service.py:184](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/services/budget_service.py#L184)
- [core/services/budget_service.py:206](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/services/budget_service.py#L206)

### 3. Updating a planned-expense plan creates overlapping versions

When a plan is updated, the previous version is closed with `valid_to = plan.start_month`, and the new version also starts at `plan.start_month`.
If month ranges are inclusive, both versions apply to the same month.

Relevant code:

- [core/views/planned_expense_plan_viewset.py:64](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_expense_plan_viewset.py#L64)
- [core/views/planned_expense_plan_viewset.py:69](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/views/planned_expense_plan_viewset.py#L69)

### 4. New users are auto-attached to the first family in the database

The `post_save` hook assigns every new user to `Family.objects.first()`.
In a real multi-tenant app this can silently attach users to the wrong tenant, and if no family exists the user may be left without `Profile`.

Relevant code:

- [core/models.py:225](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/models.py#L225)

## Operational Notes

- `README.md` is currently almost empty, so code is the source of truth.
- There is no meaningful automated test suite yet in [core/tests.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/tests.py).
- Local verification in this workspace was limited because `python3 manage.py check` failed: Django is not installed in the active environment.
- There is a duplicate `BudgetView` definition inside [core/serializers/budget_serializer.py](/Users/juancruzballadares/Desktop/Proyectos/back_ControlAnts2.0/core/serializers/budget_serializer.py), but it does not appear to be wired into routing.

## Recommended Next Steps

1. Standardize all family access on `request.user.profile.family`.
2. Decide whether the legacy and new planned-expense systems will coexist or one will replace the other.
3. Fix budget aggregation so `unplanned_total` excludes expenses already represented in planned summaries.
4. Add tests around month closing, income-plan resolution, and budget totals.
5. Replace the implicit `Family.objects.first()` onboarding behavior with an explicit family assignment flow.
