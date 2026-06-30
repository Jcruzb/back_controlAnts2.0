# Codebase Memory MCP

## Propósito

Codebase Memory mantiene un grafo local de símbolos y relaciones para consultar
rápidamente los dos repositorios de ControlAnts 2.0. El grafo sirve para descubrir
código e impacto; nunca sustituye la lectura de los archivos ni las pruebas.

## Instalación verificada

- Release oficial estable: `v0.8.1`.
- Plataforma: macOS ARM64, variante estándar sin UI.
- Binario activo: `$HOME/.local/bin/codebase-memory-mcp`.
- Copia versionada verificada:
  `$HOME/.local/share/codebase-memory-mcp/0.8.1/codebase-memory-mcp`.
- SHA-256 del archivo oficial `darwin-arm64.tar.gz`:
  `fbd047509852021b5446a11141bcb0a3d1dcaebf6e5112460960f29f052c1c58`.
- Los índices y la configuración interna viven fuera del repositorio, en
  `$HOME/.cache/codebase-memory-mcp/`.

La configuración MCP se añadió a `$HOME/.codex/config.toml`:

```toml
[mcp_servers.codebase-memory-mcp]
command = "/Users/<usuario>/.local/bin/codebase-memory-mcp"
```

También se añadieron `AGENTS.md` y `.cbmignore` en cada repositorio. No se
modificaron los archivos de instrucciones preexistentes ni los `.gitignore`.

## Proyectos indexados

- `back_ControlAnts2.0`: Django, Django REST Framework y PostgreSQL.
- `front-controlAnts2.0`: React, Vite, Tailwind CSS y Axios.

Son repositorios Git independientes. Deben indexarse por separado:

```bash
codebase-memory-mcp cli index_repository \
  '{"repo_path":"/ruta/absoluta/back_ControlAnts2.0"}'
codebase-memory-mcp cli index_repository \
  '{"repo_path":"/ruta/absoluta/front-controlAnts2.0"}'
```

La reindexación usa el mismo comando y es incremental cuando puede serlo.

## Exclusiones

Cada `.cbmignore` excluye `.git`, `.codex`, `.codebase-memory`, `.env` y variantes
sensibles, claves, certificados y patrones de credenciales. El ejemplo público
`.env.example` se conserva. También se excluyen `node_modules`, entornos Python, cachés,
`dist`, `build`, cobertura, logs, archivos temporales, bases de datos locales,
`media`, `uploads`, `exports`, `backups` y artefactos generados. La herramienta
también aplica exclusiones internas y respeta `.gitignore`.

No se habilitó la persistencia compartida del grafo, por lo que no se crea ni se
versiona `.codebase-memory/graph.db.zst`.

## Estado y consultas

```bash
codex mcp get codebase-memory-mcp
codebase-memory-mcp --version
codebase-memory-mcp config list
codebase-memory-mcp cli list_projects
codebase-memory-mcp cli index_status \
  '{"project":"NOMBRE_DEVUELTO_POR_list_projects"}'
```

Ejemplos útiles:

```bash
codebase-memory-mcp cli search_graph \
  '{"project":"PROYECTO_BACKEND","name_pattern":".*(Expense|RecurringPayment|Budget).*"}'
codebase-memory-mcp cli trace_path \
  '{"project":"PROYECTO_BACKEND","function_name":"build_budget","direction":"both"}'
codebase-memory-mcp cli search_code \
  '{"project":"PROYECTO_FRONTEND","pattern":"api.get(\"/budget/\"","limit":20}'
codebase-memory-mcp cli search_graph \
  '{"project":"PROYECTO_FRONTEND","name_pattern":".*(Dashboard|Budget|Expense|Recurring).*"}'
```

Usa primero el grafo para descubrimiento. Si faltan datos, hay falsos positivos o
se necesita comprobar comportamiento exacto, continúa con búsqueda textual y abre
los archivos reales antes de editar.

## Actualización automática

`auto_index=true` está activo. Mientras Codex mantenga el servidor MCP en
ejecución, el watcher registra los proyectos ya indexados y procesa cambios. La
prueba realizada en backend creó, modificó y eliminó un archivo temporal; el
símbolo inicial apareció, fue sustituido por el nuevo y finalmente desapareció.
Otra validación del frontend observó que una eliminación tardaba más de un minuto
y necesitó reindexación manual. Por tanto, el watcher es útil, pero la
reindexación explícita sigue siendo el mecanismo fiable después de borrados o
renombrados importantes.

Si el watcher no está activo o el índice parece obsoleto, ejecuta manualmente
`index_repository` con la ruta absoluta del repositorio. Reinicia Codex después de
cambiar su configuración MCP.

## Actualizar la herramienta

Antes de actualizar, revisa la release estable oficial, descarga el asset de la
plataforma y `checksums.txt`, verifica SHA-256 y conserva una copia del binario
actual. El comando oficial es:

```bash
codebase-memory-mcp update
```

Ese comando instala la última release disponible y puede refrescar integraciones;
para mantener el proceso auditable se recomienda repetir la descarga fijada y la
configuración manual usadas en esta instalación.

## Desactivar, desinstalar y restaurar

Desactivar la integración sin borrar índices:

```bash
codex mcp remove codebase-memory-mcp
```

Eliminar los índices de ControlAnts antes de retirar la herramienta:

```bash
codebase-memory-mcp cli delete_project '{"project":"PROYECTO_BACKEND"}'
codebase-memory-mcp cli delete_project '{"project":"PROYECTO_FRONTEND"}'
```

Después se pueden borrar los dos binarios y, si ya no contiene otros proyectos,
`$HOME/.cache/codebase-memory-mcp/`. El comando oficial
`codebase-memory-mcp uninstall` elimina configuraciones creadas por su instalador,
pero no elimina el binario ni las bases SQLite. Esta integración fue manual, por
lo que se debe preferir `codex mcp remove`.

La copia anterior de Codex está en:

```text
$HOME/.codex/backups/controlants-codebase-memory-mcp/2026-06-30T0931/config.toml.before
```

Restaurarla reemplaza toda la configuración por la fotografía previa; úsala solo
si no hubo otros cambios posteriores que deban conservarse. Los `AGENTS.md` y
`.cbmignore` añadidos a ambos repositorios se pueden retirar por separado.

## Limitaciones observadas

- La búsqueda estructural encontró tanto el `BudgetView` real como un duplicado
  muerto bajo `core/serializers/budget_serializer.py`; hay que verificar rutas.
- La inteligencia cruzada no creó enlaces `CROSS_HTTP_CALLS` entre Axios y las
  rutas DRF. Los consumidores `/budget/` se confirmaron mediante `search_code` y
  lectura directa en `Budget.jsx` y `Dashboard.jsx`.
- No existe una clase `BaseService`; el cliente compartido es `src/services/api.js`.
- En v0.8.1, la ayuda publicada menciona `cli --raw`, pero el ejecutable usa
  `cli --json` para devolver el sobre MCP sin simplificar.
- El protocolo MCP anuncia `serverInfo.version=0.10.0`, aunque el binario y la
  release verificada informan `0.8.1`; se toma la release y su checksum como fuente
  de verdad.
- Durante esta instalación, `install --dry-run` copió el binario a
  `$HOME/.local/bin` pese a indicar que no modificaría archivos. No se usó el
  instalador automático para configurar agentes.
