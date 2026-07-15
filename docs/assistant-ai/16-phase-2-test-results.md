# Resultados de pruebas de la fase backend

Fecha de validación: 14 de julio de 2026.

## Resultado

| Grupo | Pruebas | Resultado |
|---|---:|---|
| Suite existente al iniciar la fase | 50 | Base conocida en verde |
| Regresión financiera y contrato mensual añadidos | 6 | OK |
| DTOs, tools, registro, mock, endpoint y seguridad | 27 | OK |
| Suite final `core` | 83 | OK |

Comandos ejecutados:

```bash
./venv/bin/python manage.py test core.test_assistant
./venv/bin/python manage.py test core.tests.BudgetHardeningTests
./venv/bin/python manage.py test core
./venv/bin/python manage.py check
./venv/bin/python manage.py makemigrations --check --dry-run
```

## Cobertura relevante

- `ONE_MONTH`: mes objetivo, anterior/posterior, pago cero/parcial/completo, no duplicación legacy/occurrence, distintas fechas de creación, zona horaria y otra familia.
- Métricas: campos heredados compatibles, aliases inequívocos, ingreso real, caja, pendiente y desviación.
- DTOs: forma estable, strings decimales, periodo, moneda, valores negativos, vacío y ausencia de PII.
- Tools: éxito, argumentos/tenant prohibidos, filtros ajenos, límites, orden, mes vacío, error de servicio y lectura sin efectos laterales.
- Registro: tool conocida/desconocida, mapa inmutable, metadatos y modo exclusivamente read.
- Mock: seis comandos, tool disponible, errores y rechazo de escritura.
- Endpoint: autenticación, CSRF de sesión, flag apagado, provider mock, provider no permitido, input, longitud, tenant, respuesta y usuario sin familia.

## Checks finales

No hay migraciones nuevas ni dependencias de IA. La suite completa es la comprobación configurada principal; el repositorio no declara un linter Python separado. También se compilaron los módulos nuevos y se revisó el diff. El frontend independiente no fue modificado.
