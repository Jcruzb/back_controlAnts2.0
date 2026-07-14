# Auditoría de preparación para asistente de IA

## 1. Resumen ejecutivo

ControlAnts 2.0 ya expone una base sólida para un asistente financiero de solo lectura: presupuesto mensual, movimientos, planificación, estados de pagos, categorías y pagadores están aislados por familia y protegidos con sesión. La integración no debe dar al modelo acceso HTTP libre. La opción recomendada es un endpoint de orquestación propio (`POST /api/assistant/messages/`) que ejecute un registro cerrado de herramientas semánticas sobre servicios y API existentes.

La preparación no es todavía suficiente para delegar respuestas financieras sin una capa adaptadora. El contrato mensual no incluye ingresos reales ni balance de caja, varias agregaciones que muestra el frontend se calculan en cliente y `remaining_amount` significa desviación presupuestaria, no dinero disponible. También existe un problema P0: los planes versionados nuevos de tipo `ONE_MONTH` pueden crearse desde el frontend, pero `BudgetService` solo agrega planes versionados `ONGOING`.

## 2. Estado de preparación del backend

**Preparación global: media-alta para consultas mensuales de lectura; baja para escritura autónoma.**

- Autenticación real: sesión Django/DRF y CSRF en métodos inseguros.
- Tenant efectivo: `request.user.profile.family`; ninguna tool debe aceptar `user_id` o `family_id` elegidos por el modelo.
- Fuente financiera principal: `BudgetService`, `recurring_payment_service` y `planned_payment_service`.
- Lecturas con efecto lateral: presupuesto y algunos estados crean `Month` y occurrences con `get_or_create`.
- Contratos de colección mixtos: paginados por defecto, pero gastos e ingresos dejan de paginar si reciben `year` y `month`; categorías, miembros y pagos recurrentes no paginan.
- Escrituras: técnicamente disponibles, pero requieren previsualización, confirmación, CSRF, clave idempotente y auditoría antes de exponerse al asistente.

## 3. Métricas de la auditoría

| Métrica | Resultado |
|---|---:|
| Rutas API canónicas revisadas | 37 |
| Operaciones método-ruta revisadas | 73 |
| Capacidades de producto detectadas | 20 |
| Preguntas representativas respondibles | 27 |
| Preguntas parcialmente respondibles | 4 |
| Preguntas no respondibles | 3 |
| Carencias priorizadas | 12 |
| Herramientas semánticas propuestas | 12 |
| Carencias P0 | 1 |
| Carencias P1 | 6 |

No se cuentan rutas duplicadas por sufijo de formato de DRF, el API root ni Django Admin.

## 4. Recomendación arquitectónica

Adoptar la **Opción B: endpoint intermedio propio del asistente**, con un registro interno de herramientas semánticas limitado. La interfaz nunca hablará directamente con el proveedor de IA ni le entregará URLs arbitrarias. Django conserva sesión, CSRF, tenant, permisos, trazas, confirmaciones y política de datos. La selección de proveedor queda detrás de una interfaz interna.

La Opción A es útil como patrón interno —modelo selecciona una tool semántica—, pero no como integración directa desde el navegador. En la arquitectura recomendada, B contiene una variante controlada de A.

## 5. Primer alcance recomendado para el MVP

1. Corregir y probar la inclusión de planes `ONE_MONTH` en el presupuesto.
2. Crear adaptadores de solo lectura para presupuesto, gastos, ingresos, pagos, categorías y miembros.
3. Añadir un resumen financiero mensual agregado en backend con ingresos reales y balance de caja claramente nombrado.
4. Normalizar fechas con zona horaria efectiva y devolver siempre el periodo resuelto.
5. Registrar intents no soportados con datos minimizados.
6. Habilitar respuestas explicativas sin recomendaciones financieras autónomas.
7. Posponer todas las escrituras; en una fase posterior empezar por `prepare_create_expense` + confirmación explícita.

## 6. Riesgos principales

- Omisión de planes nuevos `ONE_MONTH` en el presupuesto.
- Confundir desviación presupuestaria (`remaining_amount`) con saldo real (`ingresos - gastos`).
- Reproducir en el modelo cálculos que hoy viven en el frontend sin contrato backend.
- Considerar `GET /budget/` una lectura pura cuando crea registros auxiliares.
- Fuga horizontal si una futura tool acepta IDs no resueltos dentro del queryset familiar.
- Repetición de escrituras por reintentos del modelo.
- Falta de zona horaria por usuario; solo hay `TIME_ZONE` global y hora local del navegador.
- Exposición innecesaria de correo en `payer_detail` y `/family/members/`.

## 7. Próximos pasos ordenados

1. Resolver P0 y añadir prueba de presupuesto para `PlannedExpensePlan.ONE_MONTH` creado sin fila legacy.
2. Definir DTOs estables para tools, sin reutilizar serializers CRUD completos.
3. Implementar agregaciones backend de resumen, categorías y pagadores.
4. Implementar orquestador con tools de lectura, límites y trazas redactadas.
5. Ejecutar la estrategia de pruebas unitarias, integración, conversación y seguridad.
6. Pilotar con consultas de lectura y revisar el registro de necesidades no cubiertas.
7. Diseñar escrituras en dos pasos solo después de estabilizar el MVP.

## 8. Alcance y fuentes revisadas

- Backend: `config/urls.py`, `core/urls.py`, modelos, serializers, views/viewsets, permisos, paginación, servicios, pruebas, settings, documentación y comandos de seed.
- Frontend independiente: `src/services`, contexto mensual, páginas de presupuesto/dashboard/listados, componentes de edición y utilidades de agregación.
- Fuente de verdad: código y pruebas; `Agent.md` se usó como guía y se contrastó.

## 9. Archivos generados

- [`00-endpoint-inventory.md`](00-endpoint-inventory.md)
- [`01-capability-map.md`](01-capability-map.md)
- [`02-answerable-questions.md`](02-answerable-questions.md)
- [`03-question-tool-matrix.md`](03-question-tool-matrix.md)
- [`04-capability-gaps.md`](04-capability-gaps.md)
- [`05-ai-tools-proposal.md`](05-ai-tools-proposal.md)
- [`06-unmet-needs-logging.md`](06-unmet-needs-logging.md)
- [`07-architecture-recommendation.md`](07-architecture-recommendation.md)
- [`08-security-and-permissions.md`](08-security-and-permissions.md)
- [`09-testing-strategy.md`](09-testing-strategy.md)

## 10. Código funcional modificado

Ninguno. No se añadieron dependencias ni migraciones y no se modificaron contratos.
