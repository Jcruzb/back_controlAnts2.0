# Inventario técnico de endpoints

## Criterio de conteo

La auditoría inicial inventarió **37 rutas API canónicas y 73 operaciones método-ruta**. Esta fase añade una ruta/operación experimental, por lo que el estado actual es **38 rutas y 74 operaciones**. Se excluyen Django Admin, el API root generado por DRF, `OPTIONS`, `HEAD` y duplicados con sufijo `.json`. Todos los endpoints están bajo `/api/`.

Abreviaturas: **S** = sesión Django mediante `SessionAuthentication`; **Auth** = `IsAuthenticated`; **Admin/R** = `IsFamilyAdminOrReadOnly` (lectura para miembros, mutación de configuración solo admin); **F** = familia de `request.user.profile.family`; **U** = usuario autenticado. Salvo registro/login/CSRF, la autenticación es S+Auth.

## Inventario completo

| Método | Ruta | Nombre interno | Propósito | Parámetros | Respuesta real resumida | Autenticación | Permisos | Alcance | Filtros | Servicio/lógica | Frontend | Aptitud IA | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GET | `/api/csrf/` | `csrf` | Emitir cookie CSRF | Ninguno | `{detail}` | Pública | `ensure_csrf_cookie` | Global | — | Django CSRF | Sí | Baja | Infraestructura, no tool financiera. |
| POST | `/api/auth/register/` | `RegisterView.post` | Crear usuario y familia e iniciar sesión | `username,password,email?,family_name?` | `{authenticated,user,profile,family}` | Pública | `AllowAny`, throttle `auth` | Nueva U/F | — | serializer + transacción | Sí | No recomendable | Cambia identidad y tenant. |
| POST | `/api/auth/login/` | `LoginView.post` | Iniciar sesión | `username,password` | payload auth | Pública | `AllowAny`, throttle `auth` | U | — | Django `authenticate/login` | Sí | No recomendable | Credenciales nunca pasan al modelo. |
| POST | `/api/auth/logout/` | `LogoutView.post` | Cerrar sesión | Ninguno | `{authenticated:false,detail}` | S | Auth | U | — | Django `logout` | Sí | Baja | Acción de sesión, fuera del MVP. |
| GET, PATCH | `/api/auth/me/` | `MeView` | Consultar/editar perfil básico | PATCH: `first_name,last_name,email` | payload auth con `role` y familia | S | Auth | U/F | — | `MeSerializer` | Sí | Media | GET útil para contexto; no entregar email al modelo por defecto. |
| POST | `/api/auth/change-password/` | `ChangePasswordView.post` | Cambiar contraseña | contraseña actual/nueva/confirmación | `{detail}` | S | Auth | U | — | validadores Django | Sí | No recomendable | Secreto de alta sensibilidad. |
| GET | `/api/budget/` | `BudgetView.get` | Resumen presupuestario mensual | query `year,month` obligatorios | totales, métricas de caja, `recurring[]`, `planned[]`, `income_plan_month` | S | Auth | F | Año/mes | `BudgetService` + `build_income_plan_month_status` | Sí | Alta con adaptador | GET público crea Month/occurrences; añade `actual_income`, `cash_balance` y aliases inequívocos de forma compatible. |
| POST | `/api/assistant/messages/` | `AssistantMessageView.post` | Ejecutar un comando mock sobre una tool read de allowlist | body `message`, `conversation_id?`; rechaza identidad/fields extra | mensaje, periodo, tool call, DTO, provider y request ID; error tipado | S + CSRF | Auth; feature flag | F derivada de sesión | Comando mock con año/mes | `AssistantApplicationService` + registro estático | No | Alta para piloto mock | Desactivado por defecto; no persiste conversación ni admite provider real/escritura. |
| POST | `/api/recurring/generate/` | `GenerateRecurringExpensesAPIView.post` | Generar gastos fijos del mes actual | Ninguno; usa fecha servidor | `{month,created,skipped,completed_skipped}` | S | Auth | F/U | Solo mes actual | lógica transaccional | No localizado | Baja | Escritura masiva; sin periodo explícito ni dry-run. |
| GET | `/api/family/members/` | `FamilyMemberListView` | Listar pagadores activos | Ninguno | array de `{id,username,names,email,display_name,role}` | S | Auth | F | activos | queryset | Sí | Media | Debe redactarse email/username si no son necesarios. |
| GET, POST | `/api/expenses/` | `ExpenseViewSet.list/create` | Listar o registrar gastos | GET `year+month`, `payer`, `page`, `page_size`; POST `description,amount,category,payer?,date,planned_expense?,planned_expense_plan?,recurring_payment?` | GET array sin paginar si año+mes, en otro caso envelope; POST `ExpenseSerializer` | S | Auth | F; creador U | Año+mes juntos; pagador | occurrence services + validación | Sí | Alta GET / Media POST | No filtra categoría, enlace, estado ni rango. `payer` por defecto U. |
| GET, PUT, PATCH, DELETE | `/api/expenses/{id}/` | `ExpenseViewSet` | Detalle/edición/eliminación de gasto | path `id`; body CRUD | `ExpenseSerializer` o 204 | S | Auth | F | ID dentro de queryset F | reglas de mes/occurrence | Sí | Alta GET / Baja mutación | Mes cerrado/completado bloquea cambios. Delete irreversible. |
| GET, POST | `/api/incomes/` | `IncomeViewSet.list/create` | Listar o registrar ingresos | GET `year+month`, paginación; POST `amount,category,income_plan?,date,description` | `IncomeSerializer`, con `category_detail` | S | Auth | F; creador U | Año+mes juntos | validación en viewset | Sí | Alta GET / Media POST | No hay suma agregada ni filtro categoría. |
| GET, PUT, PATCH, DELETE | `/api/incomes/{id}/` | `IncomeViewSet` | Detalle/edición/eliminación de ingreso | path `id`; body CRUD | `IncomeSerializer` o 204 | S | Auth | F | ID F | reglas de mes y plan | Sí | Alta GET / Baja mutación | Mes cerrado bloquea; delete irreversible. |
| GET, POST | `/api/categories/` | `CategoryViewSet.list/create` | Listar/crear categorías configurables | POST `name,icon,color,description`; paginación desactivada | array o categoría | S | Auth + Admin/R | F | — | queryset/serializer | Sí | Alta GET / Media POST | No distingue categoría de ingreso/gasto. Crear solo admin. |
| GET, PUT, PATCH, DELETE | `/api/categories/{id}/` | `CategoryViewSet` | Detalle/editar/eliminar categoría | path `id`; body CRUD | categoría o 204 | S | Auth + Admin/R | F | ID F | ORM; FK `PROTECT` | PATCH sí; delete no localizado | Alta GET / Baja mutación | Borrado referenciado puede fallar; sin flujo de sustitución. |
| GET, POST | `/api/recurring-payments/` | `RecurringPaymentViewSet.list/create` | Listar/crear definiciones de pagos fijos | POST `name,amount,due_day,category,payer?,start_date,end_date?` | array sin paginar / recurso | S | Auth + Admin/R | F | — | viewset | Sí | Alta GET / Media POST | Incluye activos e inactivos; mutación solo admin. |
| GET, PUT, PATCH, DELETE | `/api/recurring-payments/{id}/` | `RecurringPaymentViewSet` | Detalle/editar/desactivar pago fijo | path/body CRUD | recurso; DELETE sin borrado físico | S | Auth + Admin/R | F | ID F | validaciones y soft delete | Sí | Alta GET / Baja mutación | DELETE pone `active=false`. |
| POST | `/api/recurring-payments/{id}/reactivate/` | `RecurringPaymentViewSet.reactivate` | Reactivar definición | path `id` | recurso o 400 | S | Auth + Admin/R | F | ID F | viewset | Sí | Baja | Configuración, confirmación reforzada. |
| GET | `/api/recurring-payments/{id}/payments/` | `RecurringPaymentViewSet.payments` | Definición más historial completo de gastos asociados | path `id` | pago recurrente + `payments[]` con Expense | S | Auth + Admin/R (safe) | F | Sin periodo/paginación | prefetch + serializers | Sí | Alta | Puede crecer sin límite; incluye todo el histórico. |
| GET, PATCH | `/api/recurring-payments/{id}/month-status/` | `RecurringPaymentViewSet.month_status` | Consultar/completar/reabrir obligación mensual | query `year,month`; PATCH `{is_completed}` | importes canónicos y estado | S | Auth + Admin/R; acción permitida a miembro | F | Año/mes | `get_recurring_payment_month_state` | Sí | Alta GET / Media PATCH | GET crea Month/occurrence. PATCH no crea gasto. |
| GET, POST | `/api/planned-expenses/` | `PlannedExpenseViewSet.list/create` | CRUD de planificación legacy mensual | POST `month,category,name,planned_amount`; paginación | envelope/recurso | S | Auth + Admin/R | F | Solo paginación | serializer | No localizado directo | Media | Sistema legacy convive con planes nuevos. |
| GET, PUT, PATCH, DELETE | `/api/planned-expenses/{id}/` | `PlannedExpenseViewSet` | Detalle/editar/eliminar plan legacy | path/body CRUD | recurso o 204 | S | Auth + Admin/R | F | ID F | reglas mes cerrado | No localizado | Media GET / Baja mutación | Mantener por compatibilidad. |
| GET, PATCH | `/api/planned-expenses/{id}/month-status/` | `PlannedExpenseViewSet.month_status` | Estado mensual legacy | query `year,month`; PATCH `{is_completed}` | importes/estado canónicos | S | Auth + Admin/R; miembro permitido | F | Periodo debe coincidir | planned payment service | Sí | Alta | Contrato equivalente al nuevo. |
| GET, POST | `/api/planned-expense-plans/` | `PlannedExpensePlanViewSet.list/create` | Listar/crear planes versionados | POST `category,name,plan_type,start_month,end_month?,planned_amount` | envelope/recurso con `versions[]` | S | Auth + Admin/R | F | Solo paginación | serializer transaccional implícito | Sí | Media | El P0 de agregación `ONE_MONTH` fue corregido en fase 2; mutación sigue fuera del asistente. |
| GET, PUT, PATCH, DELETE | `/api/planned-expense-plans/{id}/` | `PlannedExpensePlanViewSet` | Detalle/editar/eliminar plan versionado | PATCH importe requiere `effective_month` | recurso con versiones o 204 | S | Auth + Admin/R | F | ID F | versionado en viewset | Sí PATCH | Media GET / Baja mutación | Actualización crea/cierra versiones. |
| POST | `/api/planned-expense-plans/{id}/deactivate/` | `deactivate` | Desactivar plan | path ID | `{status:"deactivated"}` | S | Auth + Admin/R | F | ID F | viewset | Sí | Baja | Confirmación y periodo de impacto. |
| POST | `/api/planned-expense-plans/{id}/reactivate/` | `reactivate` | Reactivar plan | path ID | `{status:"reactivated"}` | S | Auth + Admin/R | F | ID F | viewset | Sí | Baja | Puede reintroducir obligaciones futuras. |
| GET, PATCH | `/api/planned-expense-plans/{id}/month-status/` | `month_status` | Consultar/completar/reabrir plan mensual | query `year,month`; PATCH `{is_completed}` | importes/estado canónicos | S | Auth + Admin/R; miembro permitido | F | Año/mes aplicable | planned payment service | Sí | Alta GET / Media PATCH | GET crea Month/occurrence. |
| GET, POST | `/api/income-plans/` | `IncomePlanViewSet.list/create` | Listar/crear planes de ingreso | POST campos plan + `planned_amount?`; paginación | envelope/recurso | S | Auth + Admin/R | F | Solo paginación | viewset/versiones | Crear sí | Media | Listado no resuelve importe efectivo por mes. |
| GET, PUT, PATCH, DELETE | `/api/income-plans/{id}/` | `IncomePlanViewSet` | Detalle/editar/eliminar plan ingreso | path/body CRUD | recurso o 204 | S | Auth + Admin/R | F | ID F | rangos/versiones | Sí | Media GET / Baja mutación | Cambios pueden afectar rangos históricos/futuros. |
| GET | `/api/income-plans/month/` | `IncomePlanViewSet.month` | Resolver planes de ingreso de un mes | query `year,month` | `{month,results[]}` con PENDING/RESOLVED/MISSING_VERSION | S | Auth + Admin/R (safe) | F | Año/mes | resolución de versiones | Sí | Alta | Duplica lógica también presente en BudgetView. GET crea Month. |
| POST | `/api/income-plans/{id}/confirm/` | `IncomePlanViewSet.confirm` | Materializar ingreso planificado | query/body `year,month`; body `description?` | `{detail,income_id}` | S | Auth + Admin/R; miembro permitido | F/U | Año/mes | `_create_income_for_plan` | Sí | Media | Escritura monetaria; duplicado bloqueado por constraint. |
| POST | `/api/income-plans/{id}/adjust/` | `IncomePlanViewSet.adjust` | Ajustar desde mes y materializar ingreso | query/body `year,month`; `amount|planned_amount,date?,description?` | `{detail,income_id}` | S | Auth + Admin/R | F/U | Año/mes | ajuste versionado transaccional | Sí | Baja | Mezcla cambio de regla futura y movimiento real. Solo admin. |
| POST | `/api/income-plans/{id}/deactivate/` | `deactivate` | Desactivar plan ingreso | ID | `{status}` | S | Auth + Admin/R | F | ID F | viewset | No localizado | Baja | Configuración futura. |
| POST | `/api/income-plans/{id}/reactivate/` | `reactivate` | Reactivar plan ingreso | ID | `{status}` | S | Auth + Admin/R | F | ID F | viewset | No localizado | Baja | Configuración futura. |
| GET, POST | `/api/income-plan-versions/` | `IncomePlanVersionViewSet.list/create` | Listar/crear versiones manuales | POST `plan,planned_amount,valid_from,valid_to?`; paginación | envelope/recurso | S | Auth + Admin/R | F | Solo paginación | validación solape/mes cerrado | POST sí | Baja | Tool de IA no debe manipular versiones crudas. |
| GET, PUT, PATCH, DELETE | `/api/income-plan-versions/{id}/` | `IncomePlanVersionViewSet` | Detalle/CRUD de versión | path/body CRUD | recurso o 204 | S | Auth + Admin/R | F | ID F | validación de rangos | No localizado | No recomendable | Contrato interno sensible. |

## Contratos transversales

### Autenticación, CSRF y throttling

`config/settings.py` fija `SessionAuthentication`, `IsAuthenticated`, paginación de 100 (máximo 500) y `ScopedRateThrottle`; solo registro/login usan scope `auth`. El frontend usa Axios con `withCredentials`, cookie `csrftoken` y cabecera `X-CSRFToken` para métodos inseguros.

### Aislamiento

Las consultas parten de `request.user.profile.family`. Serializers de gastos, planes y pagos limitan relaciones seleccionables a la familia; views de ingresos/versiones vuelven a validar la pertenencia. La IA nunca debe enviar `user_id`/`family_id` para elegir tenant. `payer` sí es un parámetro funcional permitido, pero debe validarse contra miembros de la familia.

### Paginación

- Por defecto: `{count,next,previous,results}` con 100 y `page_size<=500`.
- Gastos/ingresos: array plano cuando están presentes **ambos** `year` y `month`.
- Categorías, miembros y recurrentes: array plano siempre.
- Budget y acciones: objetos específicos.

Una tool debe ocultar esta variabilidad y devolver DTOs consistentes.

## Evidencia técnica principal

- Rutas: `config/urls.py`, `core/urls.py` y router DRF.
- Auth/permisos: `config/settings.py`, `core/permissions.py`, `core/views/auth_view.py`.
- Contratos: `core/serializers/*`, `core/views/*`.
- Finanzas: `core/services/budget_service.py`, `recurring_payment_service.py`, `planned_payment_service.py`.
- Pruebas: `core/tests.py` cubre tenant, pagador, presupuesto, ajustes, estados mensuales, meses cerrados y roles.
- Consumo frontend: `src/services/*`, `src/pages/Budget.jsx`, `Dashboard.jsx`, `ExpensesList.jsx`, `IncomesList.jsx` del repositorio independiente.

## Discrepancias y superficies no HTTP

- `Agent.md` agrupa de forma abreviada PUT/PATCH/DELETE bajo rutas de colección como `/expenses/`; el router real aplica esas operaciones a `/expenses/{id}/`. Este inventario usa el resolver/código real.
- Hallazgo histórico resuelto: el agregador filtraba solo `ONGOING` aunque serializer y frontend admitían `ONE_MONTH`. La corrección y regresión están en `10-one-month-fix.md`.
- No existe endpoint público de cierre/reapertura de `Month`, aunque el modelo y las reglas de bloqueo sí existen.
- Los comandos `seed_all`, `seed_demo`, `seed_users`, `seed_categories` y `seed_recurring_payments` son tooling local/administrativo, no capacidades runtime y nunca deben exponerse como tools de IA.
- Variables relevantes: `TIME_ZONE`, cookie/CSRF/CORS, `AUTH_THROTTLE_RATE`, `DEBUG` y `ALLOW_DEMO_SEEDS`. No hay configuración ni SDK de proveedor de IA en el repositorio actual.
