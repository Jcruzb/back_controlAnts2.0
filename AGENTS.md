# ControlAnts 2.0 Backend

Las instrucciones funcionales, contratos y riesgos existentes se mantienen en `Agent.md`. Este documento añade reglas de tooling compatibles; no sustituye esas instrucciones.

## Principios del proyecto

- Prioriza estabilidad y preserva los flujos que ya funcionan.
- Evita sobreingeniería y cambios de contrato innecesarios.
- Las categorías son configurables y nunca deben quedar hardcodeadas.
- Si un cambio afecta contratos o comportamiento de backend y frontend, indícalo expresamente antes de cerrar la tarea.
- Respeta el aislamiento por familia, las reglas de meses cerrados y los contratos sensibles definidos en `Agent.md`.

## Codebase Memory MCP

- Usa primero Codebase Memory MCP para localizar símbolos, entender relaciones entre módulos, seguir llamadas, detectar consumidores de endpoints, analizar impacto transversal y encontrar implementaciones relacionadas.
- Recurre a búsqueda textual y lectura directa cuando el índice sea insuficiente, necesites la implementación exacta, revises configuración o textos, o sospeches que el índice está desactualizado.
- Nunca modifiques código basándote únicamente en el grafo. Abre y lee los archivos afectados, verifica modelos, serializers, views, servicios y contratos reales y ejecuta las pruebas pertinentes.
- Este backend y el frontend `front-controlAnts2.0` son repositorios independientes: selecciona explícitamente el proyecto correcto en las consultas y contrasta relaciones HTTP entre ambos cuando el cambio sea transversal.

