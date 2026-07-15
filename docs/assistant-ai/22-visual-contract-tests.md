# Pruebas del contrato visual

## Cobertura añadida

- sobre: versión, source, intent, meta, periodo, orden, IDs únicos y límites;
- nueve bloques: caso válido, obligatorios, enums, longitudes, dinero no float y serialización;
- tablas: columnas/filas máximas, columnas vacías y formatos;
- gráficas: explicación, series, importes y orden temporal;
- registro: nueve tipos, versión, inmutabilidad y desconocidos;
- acciones: allowlist real, intents, periodo, primary única, danger y URL externa;
- normalización: tildes, mayúsculas, puntuación y espacios;
- fechas: actual, anterior, enero/diciembre, año explícito, timezone y ambigüedad;
- routing: variantes frecuentes, high/medium/none y doce intents;
- alertas: exceso de caja, umbrales, pendientes, falta de ingreso e insuficiencia;
- respuestas: seis iniciales, detalles, histórico condicional, límite de alertas y PII;
- endpoint: bypass del provider, fallback mock, intent directo, errores y tenant;
- lectura pura: no crea Month/occurrences ni modifica gastos/categorías.

## Comandos

```bash
./venv/bin/python manage.py test core.test_assistant_visual
./venv/bin/python manage.py test core.test_assistant core.test_assistant_visual
./venv/bin/python manage.py test core
```

La suite específica nueva contiene 30 pruebas. Sumada a las 83 existentes, la suite final contiene 113 pruebas y finaliza en verde.
