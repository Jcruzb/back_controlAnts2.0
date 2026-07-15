# Recomendación de arquitectura

> La recomendación se materializa en fase 2 con endpoint Django, registro estático y provider mock. No existe todavía conexión a proveedor real.

## Decisión

Recomendada: **Opción B, endpoint intermedio propio del asistente**, con herramientas semánticas internas.

```text
React
  → POST /api/assistant/messages/ (sesión + CSRF)
  → AssistantApplicationService
      → normalizador de fecha/intención
      → proveedor de IA detrás de interfaz
      → ToolRegistry cerrado
          → selectors/services ControlAnts
      → redactor y response formatter
      → unmet-needs/audit log
  → respuesta y evidencias
```

El modelo puede seleccionar tools como en la Opción A, pero solo dentro del backend. El frontend no recibe secretos del proveedor, no llama al modelo directamente y no controla tenant/tool URLs.

## Comparación

| Criterio | A: tools desde orquestador externo/cliente | B: endpoint propio | Decisión |
|---|---|---|---|
| Seguridad | Riesgo de exponer API, credenciales y superficie | Sesión/CSRF/tenant quedan en Django | B |
| Permisos | Puede duplicar reglas fuera del backend | Reutiliza permisos/services | B |
| Acoplamiento | Acopla tool schemas a endpoints públicos | DTOs internos aíslan contratos | B |
| Trazabilidad | Fragmentada entre navegador/proveedor/API | trace id único y audit central | B |
| Pruebas | E2E depende de proveedor/cliente | orquestador y registry testeables con mocks | B |
| Mantenimiento | Menor código inicial, más deriva | Más capa inicial, menor riesgo operativo | B |
| Cambio de proveedor | Puede quedar incrustado en frontend | interfaz `AIProvider` intercambiable | B |
| Contratos internos | Mayor exposición | no salen del backend | B |
| Necesidades no cubiertas | Difícil correlación | clasificación central por turno/tool | B |
| UX | streaming directo sencillo, pero frágil | streaming/SSE puede añadirse con control | Empate técnico; B por seguridad |
| Escalabilidad | llamadas dispersas | límites, cache, jobs y observabilidad central | B |

## Componentes sugeridos para fase 2

- `AssistantMessageView`: transporte, sesión, CSRF y rate limit.
- `AssistantApplicationService`: ciclo del turno; sin lógica financiera.
- `ToolRegistry`: schemas versionados y allowlist.
- `ToolExecutor`: timeout, límites, auth context y errores comunes.
- `DatePeriodResolver`: expresiones relativas → periodo explícito.
- `FinancialDTOMapper`: Decimal/semántica estable y redacción.
- `ConfirmationService`: prepare/confirm/idempotency para fase de escritura.
- `UnmetNeedRecorder`: clasificación minimizada.
- `AIProvider` interface: implementación del proveedor aislada.

No introducir un framework complejo al inicio. Un registry Python explícito y services pequeños bastan para el MVP.

## Manejo determinista de fechas

### Fuente de zona horaria

Hoy no existe timezone por usuario. Hasta añadirla, usar una zona efectiva declarada por despliegue/familia (actualmente `settings.TIME_ZONE`) y, si el navegador envía zona IANA validada, tratarla como preferencia de presentación, no como selector de tenant. La respuesta debe declarar la zona usada cuando una expresión relativa pueda cambiar de mes.

### Reglas

| Expresión | Resolución |
|---|---|
| `este mes` | año/mes de `now` en timezone efectiva |
| `el mes pasado` | restar un mes calendario, con cambio de año |
| `septiembre de 2026` | `year=2026, month=9` |
| `septiembre` | septiembre del año conversacional si está fijado; si no, la ocurrencia más cercana no futura solo si la UI comunica la regla; ante impacto material, pedir año |
| `el próximo mes` | sumar un mes calendario |
| `este año` | rango enero–diciembre; si no hay tool de rango, explicar limitación o acotar pregunta |
| `¿y el anterior?` | mes anterior al último periodo confirmado, no al reloj actual |

Internamente siempre números, validación `1<=month<=12`, `1<=year<=9999`, fechas completas ISO y límites de rango. Nunca usar parsing probabilístico para ejecutar una escritura.

### Respuesta de periodo

Toda respuesta comienza con `Septiembre de 2026` y metadato interno `{year:2026,month:9,timezone:"Europe/Madrid"}`. Si el usuario cambia de mes, se reemplaza el contexto activo y se repite el nuevo periodo.

## Estrategia de respuesta

Orden recomendado:

1. periodo interpretado;
2. respuesta directa en una frase;
3. 3–6 métricas verificables;
4. aclaración de dato faltante/semántica;
5. fuente funcional, no detalles internos;
6. opción breve de ampliar.

```text
Septiembre de 2026

Se han registrado 1.760,00 € de gasto real sobre 2.450,00 € planificados.

Planificado: 2.450,00 €
Pagado: 1.760,00 €
Pendiente de obligaciones: 690,00 €
Variación del presupuesto: +690,00 €
Ingresos registrados: dato no incluido en esta consulta

Hechos basados en el presupuesto mensual de ControlAnts.
```

Reglas:

- separar planificado, pagado, pendiente, desviación y balance;
- no ocultar null, `MISSING_VERSION`, truncamiento o periodo sin datos;
- no alarmismo ni asesoramiento como hecho;
- etiquetar “Interpretación” cuando se resuma un patrón;
- no recalcular importes canónicos de pagos;
- detalle bajo demanda, no volcados extensos.

## Evolución por fases

1. **MVP read-only:** tools 1–8, respuesta corta, logging, proveedor mock en pruebas.
2. **Agregaciones:** resumen mensual, breakdowns y compare.
3. **Escritura limitada:** create expense prepare/confirm.
4. **Estados:** completar/reabrir con auditoría.
5. **Ediciones:** solo tras versionado/undo.
6. **Histórico/forecast:** únicamente con services evaluados y métricas de calidad.
