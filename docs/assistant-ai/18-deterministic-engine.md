# Motor determinista

## Arquitectura

`DeterministicAssistantService` separa cuatro responsabilidades:

1. `normalizer.py`: minúsculas, tildes, puntuación, espacios y periodos.
2. `router.py`: reglas pequeñas de intención con confianza explícita.
3. `responses.py` / `details.py`: composición progresiva de bloques.
4. `alerts.py`: condiciones financieras objetivas.

Los builders visuales no calculan finanzas. `ToolExecutionCache` invoca el registro existente, conserva cada resultado por tool+argumentos durante la respuesta y propaga errores tipados. Presupuesto, caja, gastos, recurrentes, categorías y pagadores siguen procediendo de las seis tools `materialize=False`.

## Normalización y confianza

Se eliminan tildes y puntuación solo para routing; el mensaje completo no se persiste. Las reglas reconocen expresiones equivalentes, no coincidencias exactas.

- `high`: patrón inequívoco; el backend responde sin provider.
- `medium`: solo hay vocabulario de dominio; no se adivina intención y se mantiene fallback.
- `low`: reservado para reglas futuras; no responde directamente.
- `none`: sin match; fallback al mock.

No se implementa NLP estadístico ni recomendaciones.

## Fechas

Se soportan `este mes`, `mes actual`, `mes pasado`, `mes anterior`, los doce meses y `mes de YYYY`. El mes anterior a enero se resuelve como diciembre del año anterior. Un mes sin año usa siempre el año calendario actual, tanto si ya pasó como si es futuro, evitando heurísticas ocultas. Dos meses distintos o referencias relativas incompatibles devuelven `ambiguous_period`.

El periodo siempre vuelve en la respuesta con la timezone global configurada. No existe aún timezone por perfil.

## Flujo del endpoint

```text
sesión + CSRF → flag → serializer → tenant de Profile
                                    ↓
                          router determinista
                          ↙ alta      ↘ no alta
                    tools read        MockAssistantProvider
                    bloques v1        contrato legacy mock
```

El provider se construye de forma lazy. Una consulta conocida no instancia ni ejecuta el mock. Un payload directo `{intent, arguments}` solo puede ejecutar uno de los intents registrados y tampoco usa provider.

## Tools y rendimiento

- `monthly_summary`: presupuesto + caja.
- `monthly_spending`: presupuesto + caja.
- `monthly_cash_balance`: presupuesto + caja.
- `pending_payments`: presupuesto + estados recurrentes; caja solo para alerta.
- `category_spending`: agregación de categorías.
- `payer_spending`: agregación de pagadores.
- detalles: listas limitadas y, cuando aporta valor, tres snapshots de caja para histórico.

La lista de gastos obtiene `total_count` mediante una ventana SQL en la misma consulta. Los DTOs visuales eliminan IDs de pagador y emails. No se ejecuta dos veces la misma combinación tool+argumentos dentro de una respuesta.

## Limitaciones

- El fallback mock sigue aceptando comandos técnicos, no conversación libre.
- No hay memoria conversacional ni referencias como «¿y el anterior?».
- Las tablas de pendiente detallan pagos recurrentes; la métrica total sí incluye todas las obligaciones planificadas.
- No hay vencimiento canónico suficiente para declarar `overdue_payments`.
- No hay forecasting, simulación ni recomendaciones.
