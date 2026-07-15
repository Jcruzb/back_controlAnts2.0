# Auditoría de preparación para asistente de IA

## 1. Resumen ejecutivo

ControlAnts 2.0 ya dispone de un contrato visual versionado y un motor determinista de solo lectura sobre seis herramientas semánticas. Preguntas frecuentes y acciones Ver más se resuelven sin provider ni tokens; `MockAssistantProvider` queda como fallback. `POST /api/assistant/messages/` continúa desactivado por defecto y conserva sesión, CSRF y tenant en Django.

El P0 de planes `ONE_MONTH` está corregido y cubierto. El contrato mensual conserva sus campos y añade nombres inequívocos para ingreso real, caja, pendiente y desviación. `remaining_amount` continúa siendo desviación presupuestaria por compatibilidad, nunca dinero disponible. Categorías y pagadores se agregan ahora en backend para las tools.

## 2. Estado de preparación del backend

**Preparación global: alta para implementar el renderer frontend y pilotar respuestas deterministas; no preparada para provider real ni escritura.**

- Autenticación real: sesión Django/DRF y CSRF en métodos inseguros.
- Tenant efectivo: `request.user.profile.family`; ninguna tool debe aceptar `user_id` o `family_id` elegidos por el modelo.
- Fuente financiera principal: `BudgetService` y sus reglas canónicas; la IA no recalcula importes.
- Las tools usan `materialize=False`; los endpoints públicos conservan por compatibilidad sus lecturas con materialización.
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
| Rutas actuales tras esta fase | 38 |
| Operaciones método-ruta actuales | 74 |
| Tools read implementadas | 6 |
| Pruebas backend finales | 83 |
| Bloques visuales v1 | 9 |
| Intents deterministas | 12 |
| Pruebas backend finales tras fase 3 | 113 |

Las 37/73 son la fotografía de la auditoría inicial. La ruta/operación adicional es el endpoint experimental del asistente. No se cuentan sufijos DRF, API root ni Django Admin.

## 4. Recomendación arquitectónica

Adoptar la **Opción B: endpoint intermedio propio del asistente**, con un registro interno de herramientas semánticas limitado. La interfaz nunca hablará directamente con el proveedor de IA ni le entregará URLs arbitrarias. Django conserva sesión, CSRF, tenant, permisos, trazas, confirmaciones y política de datos. La selección de proveedor queda detrás de una interfaz interna.

La Opción A es útil como patrón interno —modelo selecciona una tool semántica—, pero no como integración directa desde el navegador. En la arquitectura recomendada, B contiene una variante controlada de A.

## 5. Primer alcance recomendado para el MVP

1. Mantener el endpoint apagado por defecto y habilitarlo solo en un entorno técnico con mock.
2. Probar los seis comandos deterministas contra datos representativos.
3. Añadir normalización de fechas con zona horaria de usuario antes del proveedor real.
4. Incorporar un proveedor real detrás de `AssistantProvider`, con allowlist y tool calling controlado.
5. Añadir límites/throttling específicos y observabilidad antes de un piloto.
6. Posponer todas las escrituras; más adelante empezar por preparación + confirmación explícita.

## 6. Riesgos principales

- Los totales históricos con planes `ONE_MONTH` omitidos pueden corregirse al desplegar.
- Confundir desviación presupuestaria (`remaining_amount`) con saldo real (`ingresos - gastos`).
- Reproducir en el modelo cálculos que hoy viven en el frontend sin contrato backend.
- El endpoint público de presupuesto sigue materializando registros; solo las tools son lectura pura.
- Fuga horizontal si una futura tool acepta IDs no resueltos dentro del queryset familiar.
- Repetición de escrituras por reintentos del modelo.
- Falta de zona horaria por usuario; solo hay `TIME_ZONE` global y hora local del navegador.
- Exposición innecesaria de correo en `payer_detail` y `/family/members/`.

## 7. Próximos pasos ordenados

1. Añadir normalizador determinista de fechas y contexto conversacional mínimo no sensible.
2. Definir throttling y métricas operativas específicos del endpoint.
3. Implementar un adaptador de proveedor real sin exponer services ni URLs arbitrarias.
4. Validar tool calling, prompt injection, costes, timeouts y redacción de trazas en staging.
5. Pilotar solo lecturas y revisar necesidades no cubiertas agregadas.
6. Diseñar escrituras en dos pasos solo después de estabilizar el piloto.

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
- [`10-one-month-fix.md`](10-one-month-fix.md)
- [`11-financial-metrics-contract.md`](11-financial-metrics-contract.md)
- [`12-assistant-dtos.md`](12-assistant-dtos.md)
- [`13-read-tools-implementation.md`](13-read-tools-implementation.md)
- [`14-mock-provider.md`](14-mock-provider.md)
- [`15-assistant-endpoint.md`](15-assistant-endpoint.md)
- [`16-phase-2-test-results.md`](16-phase-2-test-results.md)
- [`17-visual-contract-v1.md`](17-visual-contract-v1.md)
- [`18-deterministic-engine.md`](18-deterministic-engine.md)
- [`19-alert-rules.md`](19-alert-rules.md)
- [`20-intent-catalog.md`](20-intent-catalog.md)
- [`21-progressive-detail.md`](21-progressive-detail.md)
- [`22-visual-contract-tests.md`](22-visual-contract-tests.md)
- [`23-phase-3-results.md`](23-phase-3-results.md)

## 10. Implementación de fase 2

Se corrigió `ONE_MONTH`, se ampliaron métricas de forma aditiva y se creó `core/assistant/`. No se añadieron dependencias, migraciones, herramientas de escritura ni proveedor real. El frontend no fue modificado.

## 11. Implementación de fase 3

`core/assistant/visual_contract/` valida el sobre y nueve bloques; `core/assistant/deterministic/` normaliza frases/fechas, enruta doce intents, evalúa alertas y construye detalle progresivo. Las consultas conocidas evitan el mock. No se añadió persistencia ni se modificó el frontend.
