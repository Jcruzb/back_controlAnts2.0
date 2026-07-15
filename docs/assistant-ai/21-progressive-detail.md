# Carga progresiva y acciones Ver más

## Respuesta inicial

La conclusión ocupa el primer `summary_card`. Después aparecen solo métricas necesarias, un máximo de dos alertas y un `action_group`. No se cargan listas completas.

- Resumen mensual: 4 métricas.
- Gasto mensual: 4 métricas; sin movimientos automáticos.
- Pendientes: 2 métricas y hasta 5 pagos fijos.
- Categorías: hasta 5 barras.
- Pagadores: hasta 10 agregados minimizados.

## Detalle

`fetch_detail` envía exclusivamente intent, año y mes al mismo endpoint. El cliente no reenvía bloques ni importes como fuente de verdad. Django vuelve a resolver tenant y datos.

`monthly_summary_detail` puede incluir:

1. conclusión neutral del periodo;
2. barras de hasta 10 categorías;
3. tabla de hasta 10 gastos principales;
4. tabla de hasta 10 pagos fijos pendientes;
5. línea de tres meses si al menos dos tienen actividad;
6. navegación permitida.

Cada gráfico tiene `explanation` determinista. Si faltan datos, se omite el bloque; el periodo vacío puede mostrar `insufficient_data`. Las tablas indican `total_rows` real y `has_more`; el frontend podrá añadir paginación en una fase posterior sin cambiar el bloque base.

## Navegación

Las acciones apuntan únicamente a rutas verificadas del frontend. No hay URLs externas, estilos danger ni acciones financieras. La implementación frontend deberá tratar `id` como clave técnica y nunca mostrarlo como columna.
