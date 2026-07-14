# Matriz pregunta → herramienta

La confianza mide si el sistema actual puede obtener un resultado técnicamente correcto. **Alta** exige contrato directo o composición exacta sobre un mes completo; **media** indica ambigüedad o múltiples contratos; **baja** indica carencia o riesgo contractual.

| Pregunta o intención | Endpoint principal | Secundarios | Parámetros | ¿Hoy? | Confianza | Riesgos | Mejora sugerida |
|---|---|---|---|---|---|---|---|
| Estado del presupuesto mensual | `/budget/` | — | año, mes | Sí* | Media | P0 ONE_MONTH | Corregir agregación |
| Total gastado | `/budget/` | — | año, mes | Sí | Alta | semántica de gasto real | DTO explícito |
| Dinero restante del presupuesto | `/budget/` | — | año, mes | Sí | Alta | no es caja | nombrar `budget_variance` |
| Saldo de caja del mes | `/incomes/` | `/budget/` | año, mes | Parcial | Media | suma cliente, término ambiguo | resumen backend |
| Total ingresado | `/incomes/` | — | año, mes | Sí por composición | Media | Decimal/paginación | `total_income` backend |
| Ingresos pendientes | `/income-plans/month/` | `/budget/` | año, mes | Sí | Alta | MISSING_VERSION | tool tipada |
| Gastos más altos | `/expenses/` | — | año, mes, limit tool | Sí | Alta | sin top-N server | order/limit seguro |
| Gasto por categoría | `/expenses/` | `/categories/` | año, mes | Sí por composición | Alta | renombres | agregación backend |
| Fijos pendientes | `/budget/` | — | año, mes | Sí | Alta | completado manual | filtrar canonical status |
| Fijos completados | `/budget/` | — | año, mes | Sí | Alta | completado ≠ pago exacto | explicar estado |
| Historial de un fijo | `/recurring-payments/{id}/payments/` | — | ID | Sí | Alta | sin paginación/periodo | añadir filtros |
| Pagado/pendiente de fijo | `/recurring-payments/{id}/month-status/` | — | ID, año, mes | Sí | Alta | GET crea occurrence | adaptador |
| Pagado/pendiente plan legacy | `/planned-expenses/{id}/month-status/` | — | ID, año, mes | Sí | Alta | sistema legacy | unificar tool |
| Pagado/pendiente plan nuevo | `/planned-expense-plans/{id}/month-status/` | — | ID, año, mes | Sí* | Media | P0 en resumen budget | corregir P0 |
| Gastos no planificados | `/budget/` | `/expenses/` | año, mes | Sí | Alta total / Media detalle | sin filtro server | query `planning_status` |
| Quién pagó un gasto | `/expenses/{id}/` | — | ID | Sí | Alta | no confundir creador | DTO sin PII extra |
| Total por persona | `/expenses/` | `/family/members/` | año, mes | Sí por composición | Alta | payer nulo | agregación backend |
| Categorías existentes | `/categories/` | — | — | Sí | Alta | no tienen tipo | añadir `usage_type` si procede |
| Crear categoría | `/categories/` | — | payload + confirmación | Sí admin | Media | duplicado/PROTECT | prepare/commit |
| Comparar dos meses | `/budget/` | `/incomes/` | dos periodos | Parcial | Media | 4 llamadas, GET muta | endpoint compare |
| Tendencia trimestral | múltiples | — | 3 meses | Parcial | Baja | N llamadas | endpoint de serie |
| Pronóstico de diciembre | — | — | horizonte | No | Baja | no existe forecast | service/modelo futuro |
| Registrar gasto | `/expenses/` | categorías/miembros | payload + confirmación | Sí | Media | duplicado, periodo | prepare/commit idempotente |
| Editar gasto | `/expenses/{id}/` | — | patch + confirmación | Sí | Media-baja | importe/mes | diff + deshacer |
| Eliminar gasto | `/expenses/{id}/` | — | ID + confirmación fuerte | Sí | Baja | irreversible | soft delete/audit |
| Completar/reabrir fijo | recurrent month-status | — | ID, periodo, boolean | Sí | Media | no crea dinero | preview de estado |
| Completar/reabrir planificado | planned month-status | — | tipo, ID, periodo, boolean | Sí | Media | dos sistemas | tool unificada |
| Cerrar/reabrir mes | — | — | periodo | No | Baja | no API; alto riesgo | política/endpoint admin futuro |
| Estado general familiar | `/budget/` | `/incomes/`, `/expenses/` | año, mes | Parcial | Media | términos y P0 | monthly financial summary |
| Recomendación de ahorro | — | datos mensuales | objetivos/preferencias | No como hecho | Baja | asesoramiento inferido | separar hechos/sugerencias |
| Ver datos de otra familia | — | — | `family_id` | No y no debe | Alta denegación | mantener tenant implícito |

`*` Exactitud condicionada a corregir la omisión de planes nuevos `ONE_MONTH`.
