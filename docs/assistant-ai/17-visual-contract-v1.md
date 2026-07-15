# Contrato visual del copiloto v1

## Sobre común

Las respuestas deterministas usan `schema_version="1.0"`, centralizado en `visual_contract/enums.py`:

```json
{
  "schema_version": "1.0",
  "response_id": "resp_<uuid>",
  "source": "deterministic",
  "intent": "monthly_summary",
  "period": {
    "year": 2026,
    "month": 7,
    "label": "Julio de 2026",
    "timezone": "Europe/Madrid"
  },
  "summary": "Vais dentro del presupuesto.",
  "blocks": [],
  "meta": {
    "has_more": true,
    "generated_at": "ISO-8601 con zona horaria",
    "request_id": "req_<uuid>"
  }
}
```

Son obligatorios `schema_version`, `response_id`, `source`, `intent`, `summary`, `blocks` y `meta`. `period` y `actions` de nivel superior son opcionales. El MVP usa acciones dentro de `action_group` para mantener el orden visual.

`source` admite `deterministic`, `ai` y `hybrid`; esta fase solo genera `deterministic`. Una respuesta determinista rechaza bloques `recommendation` y `question`.

## Periodo y formato

El backend genera la etiqueta española y usa `settings.TIME_ZONE`; no acepta label ni timezone del cliente. Hasta que exista zona por usuario, la limitación es una zona global de aplicación. Dinero y porcentajes viajan como strings con dos decimales. `formatted_value` se centraliza en `visual_contract/formatting.py`; la moneda procede de `DEFAULT_CURRENCY` y actualmente solo EUR tiene símbolo específico.

## Catálogo cerrado de bloques

| Tipo | Campos esenciales | Validaciones específicas |
|---|---|---|
| `summary_card` | id, title, headline, description?, status | máximo uno; primero; title 60, headline 90, description 180; estados neutral/positive/attention/negative/critical |
| `metric_grid` | id, items | 2–4 métricas; value decimal string; keys únicas; trend distingue direction y meaning |
| `alert` | id, code, severity, title, message, facts, action? | severidad info/warning/critical; facts minimizados; máximo dos bloques visibles |
| `simple_table` | id, title, columns, rows, limit, total_rows, has_more | máximo 5 columnas y 10 filas; formatos cerrados; sin columnas vacías; moneda/porcentaje no float |
| `bar_chart` | id, title, explanation, x_axis, series, data | explicación obligatoria; máximo 10 categorías y 2 series; sin colores/config de librería |
| `line_chart` | id, title, explanation, x_axis, series, data | explicación; 2+ periodos ordenados; máximo 3 series; `data_kind` obligatorio |
| `recommendation` | level, headline, explanation, reasons, confidence | validable solo para fuente ai/hybrid; nunca generado por el motor actual |
| `question` | question, reason, input | una por respuesta; tipos de entrada cerrados; nunca generado en esta fase |
| `action_group` | layout, actions | 1–3 acciones, IDs únicos y máximo una primaria |

Todos declaran `BLOCK_VERSION="1.0"`. `BLOCK_REGISTRY` es un `MappingProxyType`; no existe registro dinámico ni sobrescritura.

Formatos de tabla: `text`, `currency`, `percentage`, `date`, `integer`, `status`. Alineaciones: `left`, `center`, `right`. `data_kind`: `actual`, `planned`, `projected`, `simulated`; esta fase solo emite históricos `actual`.

## Acciones

Tipos contractuales: `fetch_detail`, `navigate`, `send_intent`, `submit_answer`, `expand`, `collapse`. El motor determinista actual solo genera `fetch_detail` y `navigate`. `danger` existe como enum futuro pero se rechaza en el MVP read-only.

La allowlist se contrastó con `front-controlAnts2.0/src/app/Router.jsx`:

```text
/
/dashboard
/expenses
/incomes
/recurring
/categories
/account
```

No se admiten URLs externas. `fetch_detail` y `send_intent` exigen un intent registrado y argumentos `year/month` válidos. Ninguna acción contiene payload financiero como fuente de verdad.

## Límites globales

| Recurso | Máximo |
|---|---:|
| Bloques | 10 |
| Alertas visibles | 2 |
| Acciones | 3 |
| Métricas | 4 |
| Columnas | 5 |
| Filas | 10 |
| Categorías de barras | 10 |
| Series de barras | 2 |
| Series de línea | 3 |

## Errores

El contrato incorpora `invalid_visual_block`, `unsupported_block_type`, `invalid_action`, `unsupported_intent`, `ambiguous_period`, `invalid_period`, `deterministic_match_failed`, `detail_not_available`, `too_many_blocks`, `too_many_alerts`, `invalid_table` e `invalid_chart`. Se devuelven dentro del sobre de error existente y nunca incluyen stack trace.

## Compatibilidad

No se eliminó ningún campo del endpoint. Las consultas naturales reconocidas devuelven el contrato visual. Los comandos técnicos históricos del mock conservan temporalmente el contrato legacy, permitiendo una migración gradual del consumidor.
