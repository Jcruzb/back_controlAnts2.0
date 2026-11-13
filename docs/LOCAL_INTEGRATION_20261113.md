# Prueba local de la integración del 13 de noviembre de 2026

Esta rama reúne ingresos, financiaciones, Nilo con revisión/confirmación y escalado
IA solicitado explícitamente. No implica fusión ni despliegue de `main`.

## Obtener las ramas

Desde cada repositorio, sin cambios locales pendientes:

```sh
git fetch origin
git switch codex/integration-20261113
git pull --ff-only origin codex/integration-20261113
```

En una máquina nueva:

```sh
git clone --branch codex/integration-20261113 https://github.com/Jcruzb/back_controlAnts2.0.git
git clone --branch codex/integration-20261113 https://github.com/Jcruzb/front_ControlAnts2.0.git
```

## Backend

Requisitos: PostgreSQL local en ejecución, comandos `createdb` y Python **3.9**.
Django 4.2 de este repositorio falla con Python 3.14 al renderizar determinadas
respuestas de error. Las verificaciones de esta integración usan Python 3.9.
En este Mac `/usr/bin/python3 --version` devuelve 3.9.6; en otro equipo usar
`python3.9` en lugar de `/usr/bin/python3` si corresponde.

En una terminal, dentro de `back_controlAnts2.0`:

```sh
/usr/bin/python3 --version
/usr/bin/python3 -m venv .venv-integration
.venv-integration/bin/python -m pip install -r requirements.txt
export DEBUG=true
export SECRET_KEY=controlants-local-integration-only
export ALLOWED_HOSTS=localhost,127.0.0.1
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_USER="$(id -un)"
export DB_PASSWORD=''
export DB_NAME=controlants_local_20261113
export SECURE_SSL_REDIRECT=false
export SESSION_COOKIE_SECURE=false
export CSRF_COOKIE_SECURE=false
export USE_X_FORWARDED_PROTO=false
export CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
export CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
export TIME_ZONE=Europe/Madrid
export ASSISTANT_ENABLED=true
export ASSISTANT_PROVIDER=mock
createdb --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" "$DB_NAME"
.venv-integration/bin/python manage.py migrate
.venv-integration/bin/python manage.py seed_all
.venv-integration/bin/python manage.py runserver 127.0.0.1:8001
```

`createdb` se ejecuta solo la primera vez. Si PostgreSQL utiliza otro usuario,
puerto o contraseña, ajustar esas cuatro variables antes de crear la base. El
usuario local debe poder crear bases de datos para ejecutar la suite; Django crea
y elimina `test_controlants_local_20261113`. No configurar aquí una base remota o
de producción. Las variables exportadas prevalecen sobre un `.env` existente.

Las migraciones `0018_financing` y `0019_nilo_proposals` crean tablas separadas.
`0020_merge_financing_nilo` une sus historiales y no altera filas de negocio.

## Frontend

En otra terminal, dentro de `front_ControlAnts2.0`:

```sh
npm ci
VITE_API_BASE_URL=/api VITE_DEV_PROXY_TARGET=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Abrir `http://127.0.0.1:5173`. El proxy de Vite conecta `/api/` al backend en
`127.0.0.1:8001`. Usar siempre el mismo hostname para mantener sesión y CSRF.

Usuario demo: `demo@controlants.local` / `ControlAntsDemo2026!`.

## Pruebas automáticas

En la terminal del backend, con las mismas variables anteriores (detener el
servidor con Ctrl+C o abrir otra terminal y volver a exportarlas):

```sh
export USE_FAST_PASSWORD_HASHER=true
.venv-integration/bin/python manage.py test --noinput
.venv-integration/bin/python manage.py makemigrations --check --dry-run
```

En el frontend:

```sh
npm run lint
npm run build
npm test
```

La suite backend incluye concurrencia PostgreSQL para cobros, pagos financiados y
confirmaciones de Nilo, además de una prueba conjunta que comprueba que el balance
suma cada movimiento real una sola vez. No sustituir PostgreSQL por SQLite al
verificar esos bloqueos.

## Comprobación manual

1. En Presupuestos > Ingresos, crear un plan: el balance no cambia. Registrar un
   cobro con importe distinto; revisar que no modifica el previsto futuro.
2. Cambiar el importe previsto desde otro mes: no aparece un ingreso real nuevo.
3. Crear una compra financiada de 300 € en tres cuotas: deuda 300 €, balance sin
   cambios. Pagar 40 €: deuda 260 €, balance reducido solo 40 €.
4. En Nilo, introducir un gasto y un ingreso separados por línea. Revisar tipo,
   importe, fecha y categoría. Preparar la propuesta y confirmar explícitamente:
   antes de ese último paso no debe aparecer ningún movimiento.
5. Marcar un alias con una categoría elegida y confirmarlo. Comprobar su sugerencia
   en la misma familia. Otra familia no debe recibir ese alias.
6. Las consultas deterministas no usan IA externa. El modo `mock` permite probar
   el flujo sin claves; no representa una respuesta de un modelo real. Para probar
   OpenAI, configurar únicamente en backend `ASSISTANT_PROVIDER=openai`,
   `OPENAI_API_KEY` y `OPENAI_MODEL`, reiniciar y solicitar el escalado en la UI.
7. Dictado depende del soporte/permisos del navegador. Revisar siempre el texto y
   los importes antes de confirmar. Las fechas ambiguas requieren corrección.

## Despliegue de producción confirmado

JuanOS completó ambos despliegues: backend `4122aa1` con migraciones hasta `0021` y frontend `677c5cd`. Se desplegaron las ramas de integración; no hubo merge a main. La reparación previa de JuanOS permitió revisar configuración, autorizar las acciones concretas del host, comprobar los planes y publicar el frontend mediante releases.

Respaldo previo más reciente: `/var/backups/controlants/juanos/b6a34377-79a7-4ee8-b722-5d2f1c02016e.dump`, 120313 bytes, índice verificado. La verificación del índice no equivale a haber restaurado ese dump real.

El ensayo API dentro del proceso Django de producción terminó con **86 comprobaciones correctas**, dos familias sintéticas, `rollback_verified=true`, cero llamadas a IA externa y salida 0. Incluyó previsión y cobro excepcional, reintentos idempotentes, cambio de previsión futura, tarjeta/compra/cuota, separación de deuda y efectivo, borrador Nilo, confirmación explícita múltiple, alias, aislamiento entre familias y rechazo de escrituras en mes cerrado. Todos los registros sintéticos se revirtieron en una transacción; no se usaron datos de familias reales. Las secuencias PostgreSQL pueden consumir identificadores incluso al revertir.

El primer intento detectó una secuencia histórica de usuarios atrasada respecto a los datos importados. Se avanzó `auth_user` de 2 a 3 bajo bloqueo de tabla, sin editar registros existentes; el ensayo posterior aprobó todas las comprobaciones. No se restauró una BD ni se redujeron secuencias.

Para recuperación, conservar las versiones y artefactos previos, así como el esquema aditivo y cualquier dato generado desde el despliegue. No revertir migraciones ni restaurar automáticamente el dump: podría perder cobros, pagos, propuestas o alias posteriores. Una restauración de datos requiere una decisión y un procedimiento separado.

Límites: el ensayo autenticó usuarios sintéticos mediante `force_authenticate`; valida contratos y reglas de API, no sustituye el login/CSRF real en navegador. La comprobación final en navegador de producción también pasó: modal de ingresos separa previsión y cobro sin guardar; financiación carga y usa categorías configuradas; Nilo responde una consulta determinista y analiza un borrador sintético de gasto 10 e ingreso 50 sin preparar ni confirmar operaciones; Dashboard y Gastos conservan los movimientos y totales existentes. No se observaron errores de navegador. No se publican importes reales de la familia en este registro. Micrófono real y reconocimiento de voz no probados; siguen vigentes los demás límites de QA anteriores. No se afirma una prueba real de proveedor IA externo.

Release estática servida: `/var/www/controlants/frontend-releases/677c5cd4e944c8fdeba27c058367a1adb1079054`. La captura de verificación se conserva localmente fuera de Git; no se suben capturas con datos financieros reales.
