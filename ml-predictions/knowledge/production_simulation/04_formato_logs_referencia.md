# Formato de Logs y Referencia de Campos — RCA Platform

Este documento describe el formato exacto de los logs estructurados del sistema,
el significado de cada campo y las reglas de interpretación para diagnóstico.
Es la referencia que el modelo de lenguaje debe usar para interpretar cualquier
log del sistema.

---

## Formato general

Todos los logs se emiten en formato JSON estructurado mediante Logstash Logback
Encoder. Cada campo es un valor de primer nivel en el JSON, directamente
indexable y consultable en Loki.

Los logs de una misma petición HTTP están vinculados por el campo `traceId`.
Una petición que involucra más de un microservicio genera logs en múltiples
servicios, todos con el mismo `traceId`.

---

## Campos del log

### Campos de identidad y contexto

| Campo | Tipo | Descripción |
|---|---|---|
| `@timestamp` | ISO-8601 UTC | Momento exacto en que se generó el log |
| `service` | string | Nombre del microservicio emisor |
| `traceId` | string (hex 32 chars) | Identificador único de la petición HTTP, propagado entre servicios |
| `spanId` | string (hex 16 chars) | Identificador del paso concreto dentro de la petición |
| `level` | enum | Severidad: `INFO`, `WARN`, `ERROR` |
| `message` | string | Descripción breve del evento |

### Campos de contexto HTTP (presentes en logs del RequestLoggingFilter)

| Campo | Tipo | Descripción |
|---|---|---|
| `event_type` | enum | Clasificación del evento (ver sección siguiente) |
| `outcome` | enum | `SUCCESS` si http_status < 400, `FAILURE` en caso contrario |
| `http_method` | enum | Verbo HTTP: `GET`, `POST`, `PUT`, `DELETE` |
| `http_uri` | string | Ruta del endpoint invocado |
| `http_status` | string | Código de respuesta HTTP |
| `duration_ms` | string (numérico) | Duración total de la petición en milisegundos |

### Campos de error (presentes en logs del ErrorLoggingAdvice)

| Campo | Tipo | Descripción |
|---|---|---|
| `error_type` | string | Nombre de la clase de excepción Java |
| `error_message` | string | Mensaje de la excepción |
| `error_origin` | string | Frames del stack trace del código propio (máx. 3), formato `Clase.método(Archivo.java:línea)` |
| `error_cause_type` | string | Clase de la excepción causante (si existe causa anidada) |
| `error_cause_message` | string | Mensaje de la excepción causante |

---

## Clasificación de eventos (event_type)

El campo `event_type` es generado automáticamente por el `RequestLoggingFilter`
basándose en el código HTTP de respuesta y el tipo de excepción.

| Valor | Condición | Nivel de log | Significado |
|---|---|---|---|
| `HTTP_REQUEST` | http_status 2xx | INFO | Petición completada con éxito |
| `VALIDATION_ERROR` | http_status 400 o 422 | WARN | Datos inválidos enviados por el cliente |
| `AUTH_ERROR` | http_status 401 o 403 | WARN | Autenticación o autorización fallida |
| `NOT_FOUND` | http_status 404 | WARN | Recurso no encontrado |
| `SERVER_ERROR` | http_status 5xx sin excepción no capturada | ERROR | Error interno del servidor |
| `UNHANDLED_ERROR` | Excepción no capturada que llegó al filtro | ERROR | Error no gestionado en el código |

---

## Dos tipos de logs por petición con error

Cuando ocurre un error, una misma petición genera dos logs con el mismo `traceId`:

**Log tipo A — del ErrorLoggingAdvice** (captura la excepción en Spring MVC):
```json
{
  "@timestamp": "2026-07-03T08:05:35.800Z",
  "service": "api-pedidos",
  "traceId": "6a476d31...",
  "level": "ERROR",
  "message": "Error capturado",
  "event_type": "UNHANDLED_ERROR",
  "error_type": "ResourceAccessException",
  "error_message": "I/O error on POST request for 'http://api-inventario:8080/inventario/1/retirar': Read timed out",
  "error_cause_type": "SocketTimeoutException",
  "error_cause_message": "Read timed out",
  "error_origin": "PedidoService.retirarStockDeInventario(PedidoService.java:57) -> PedidoService.crearPedido(PedidoService.java:34)"
}
```

**Log tipo B — del RequestLoggingFilter** (registra el contexto HTTP de la petición):
```json
{
  "@timestamp": "2026-07-03T08:05:35.850Z",
  "service": "api-pedidos",
  "traceId": "6a476d31...",
  "level": "ERROR",
  "message": "Peticion completada",
  "event_type": "SERVER_ERROR",
  "outcome": "FAILURE",
  "http_method": "POST",
  "http_uri": "/pedidos",
  "http_status": "500",
  "duration_ms": "5273"
}
```

El Log tipo A tiene el detalle del error (qué excepción y dónde).
El Log tipo B tiene el contexto HTTP (qué endpoint, cuánto tardó, qué status devolvió).
Juntos, vinculados por `traceId`, forman el diagnóstico completo.

---

## Reglas de interpretación

### Regla 1: duration_ms es el indicador más fiable de anomalía

Un `duration_ms` significativamente superior al baseline histórico del servicio
indica un problema, incluso cuando `outcome` es `SUCCESS` y `http_status` es 200.
La degradación de latencia precede a los fallos.

Baselines aproximados de este sistema:
- api-autenticacion: < 200ms
- api-inventario (lectura): < 150ms
- api-inventario (escritura con retirada de stock): < 300ms
- api-pedidos (creación de pedido, incluye llamada a inventario): < 500ms

Cualquier valor 5 veces superior al baseline es una anomalía significativa.

### Regla 2: error_origin revela la causa raíz en el código

El campo `error_origin` contiene los frames del stack trace filtrados al código
propio del sistema (paquete `rca.*`). Los frames de Spring, Tomcat y Java internos
están excluidos deliberadamente para reducir el ruido.

El primer frame en `error_origin` es la línea exacta donde ocurrió el error.
Los frames siguientes (separados por `->`) son los llamadores en la cadena.

Ejemplo:
```
"error_origin": "PedidoService.retirarStockDeInventario(PedidoService.java:57) -> PedidoService.crearPedido(PedidoService.java:34)"
```
Esto significa: el error ocurrió en la línea 57 de PedidoService, en el método
`retirarStockDeInventario`, que fue llamado desde `crearPedido` en la línea 34.

### Regla 3: el traceId vincula causa y efecto entre servicios

Si dos logs de servicios distintos tienen el mismo `traceId`, pertenecen a la
misma operación de negocio. Para diagnosticar un fallo en cascada:

1. Recopilar todos los logs con el mismo `traceId`.
2. Ordenar por `@timestamp` ascendente.
3. El log con `level=ERROR` más antiguo indica el servicio origen del problema.
4. El servicio con mayor `duration_ms` es el cuello de botella.

### Regla 4: AUTH_ERROR con duration_ms < 10ms es siempre un problema del cliente

Si `event_type=AUTH_ERROR` y `duration_ms` es inferior a 10ms, el rechazo
ocurrió en el filtro de seguridad antes de llegar al código de negocio.
No es un problema del servidor. El cliente tiene un token inválido o expirado.

### Regla 5: error_cause_type revela la raíz técnica real

Muchas excepciones de alto nivel envuelven la causa real. La causa real está
en `error_cause_type` y `error_cause_message`:

- `ResourceAccessException` → causa real: `SocketTimeoutException` (timeout de red)
- `CannotCreateTransactionException` → causa real: `SQLTransientConnectionException` (BD no disponible)
- `HttpServerErrorException$InternalServerError` → indica que otro servicio devolvió 500;
  hay que buscar ese servicio con el mismo `traceId`

---

## Campos del modelo ML y su interpretación

El motor analítico en Python transforma los logs y genera features adicionales:

| Feature | Descripción | Valor anómalo |
|---|---|---|
| `duracion_relativa` | Ratio entre `duration_ms` y el baseline normal del servicio | > 3.0 |
| `is_cascada` | 1 si el `traceId` aparece con ERROR en más de un servicio | 1 |
| `tiene_error_5xx` | 1 si `http_status` contiene un código 5xx | 1 |
| `log_count` | Número de logs individuales agrupados bajo el mismo `traceId + service` | > 3 puede indicar reintentos |
| `anomaly_score` | Score del Isolation Forest (más negativo = más anómalo) | < -0.1 |
| `prediccion` | Clasificación final del modelo | -1 = anomalía, 1 = normal |

---

## Ejemplos de logs por escenario

### Petición normal exitosa

```json
{
  "@timestamp": "2026-07-03T08:40:46.042Z",
  "service": "api-inventario",
  "traceId": "6a477587...",
  "level": "INFO",
  "event_type": "HTTP_REQUEST",
  "outcome": "SUCCESS",
  "http_method": "GET",
  "http_uri": "/inventario",
  "http_status": "200",
  "duration_ms": "89"
}
```

### Timeout entre servicios

```json
{
  "@timestamp": "2026-07-03T08:05:35.850Z",
  "service": "api-pedidos",
  "traceId": "6a476d31...",
  "level": "ERROR",
  "event_type": "UNHANDLED_ERROR",
  "error_type": "ResourceAccessException",
  "error_message": "I/O error on POST request: Read timed out",
  "error_cause_type": "SocketTimeoutException",
  "error_origin": "PedidoService.retirarStockDeInventario(PedidoService.java:57)"
}
```

### Error de validación

```json
{
  "@timestamp": "2026-07-03T09:15:22.100Z",
  "service": "api-inventario",
  "traceId": "6a47aa12...",
  "level": "WARN",
  "event_type": "VALIDATION_ERROR",
  "outcome": "FAILURE",
  "http_method": "POST",
  "http_uri": "/inventario",
  "http_status": "400",
  "duration_ms": "8",
  "error_type": "MethodArgumentNotValidException",
  "error_message": "Field 'nombre' must not be blank"
}
```

### Pool de BD agotado

```json
{
  "@timestamp": "2026-07-03T08:05:07.821Z",
  "service": "api-inventario",
  "traceId": "6a476d2b...",
  "level": "ERROR",
  "event_type": "SERVER_ERROR",
  "outcome": "FAILURE",
  "http_method": "POST",
  "http_uri": "/inventario/1/retirar",
  "http_status": "500",
  "duration_ms": "30044",
  "error_type": "CannotCreateTransactionException",
  "error_message": "Could not open JPA EntityManager for transaction",
  "error_cause_type": "SQLTransientConnectionException",
  "error_cause_message": "HikariPool-1 - Connection is not available, request timed out after 30000ms"
}
```
