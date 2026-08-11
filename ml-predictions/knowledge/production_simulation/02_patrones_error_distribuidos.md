# Patrones de Error en Sistemas Distribuidos

Este documento describe los patrones de fallo más comunes en arquitecturas
de microservicios con comunicación HTTP síncrona, sus causas raíz, cómo
se manifiestan en los logs y cómo diagnosticarlos correctamente.

---

## 1. Timeout en cascada (Cascading Timeout)

### Qué es

Un servicio A llama a un servicio B. B tarda demasiado en responder porque
está esperando a su base de datos o a otro servicio C. A agota su timeout
configurado y lanza una excepción, devolviendo un error al cliente. Desde
el punto de vista del cliente, tanto A como B han fallado, pero la causa
raíz está en el origen de la cadena.

### Cómo se manifiesta en logs

```
Servicio A (api-pedidos):
  event_type: UNHANDLED_ERROR
  error_type: ResourceAccessException
  error_message: "I/O error on POST request: Read timed out"
  error_cause_type: SocketTimeoutException
  duration_ms: 5273  ← exactamente el timeout configurado
  level: ERROR

Servicio B (api-inventario):
  event_type: SERVER_ERROR
  duration_ms: 29014  ← mucho más alto, aquí está el cuello de botella
  level: ERROR
  (mismo traceId que el log de api-pedidos)
```

### Señales diagnósticas

- El `duration_ms` del servicio origen es significativamente mayor al del
  servicio consumidor.
- El `duration_ms` del servicio consumidor es aproximadamente igual al
  valor del timeout configurado (5000ms en este sistema).
- El `error_type` en el consumidor es `ResourceAccessException` o
  `SocketTimeoutException`, nunca el error real del servicio origen.
- Ambos logs comparten el mismo `traceId`.

### Diagnóstico correcto

La causa raíz **NO** es el servicio que lanza `ResourceAccessException`.
Ese servicio es la víctima. La causa raíz es el servicio con mayor
`duration_ms` en el mismo `traceId`.

---

## 2. Saturación del pool de conexiones (Connection Pool Exhaustion)

### Qué es

Un servicio recibe más peticiones concurrentes de las que puede atender con
las conexiones disponibles en su pool de base de datos. Las peticiones nuevas
se quedan esperando una conexión libre. Si el tiempo de espera supera el
timeout del pool, se lanza una excepción de transacción.

HikariCP (el pool de conexiones por defecto en Spring Boot) tiene un pool
de 10 conexiones por defecto. Si las 10 están ocupadas y una nueva petición
espera más de 30 segundos (timeout por defecto), lanza excepción.

### Cómo se manifiesta en logs

```
event_type: SERVER_ERROR o UNHANDLED_ERROR
error_type: CannotCreateTransactionException
error_message: "Could not open JPA EntityManager for transaction"
error_cause_type: SQLTransientConnectionException
error_cause_message: "HikariPool-1 - Connection is not available, request timed out after 30000ms"
duration_ms: > 30000  ← el tiempo de espera del pool
level: ERROR
```

### Señales diagnósticas

- `error_type` es `CannotCreateTransactionException` o `DataSourceLookupFailureException`.
- `error_cause_message` menciona `HikariPool` y `Connection is not available`.
- `duration_ms` es cercano o superior a 30000ms (30 segundos, timeout por defecto de HikariCP).
- Múltiples logs con el mismo `error_type` en un intervalo de tiempo corto
  indican saturación sistémica, no un error puntual.

### Causas comunes

- Consultas SQL lentas que no liberan la conexión durante demasiado tiempo.
- Transacciones abiertas que no se cierran correctamente (conexión retenida).
- Pico de tráfico que supera la capacidad del pool.
- Deadlock en PostgreSQL que mantiene transacciones bloqueadas indefinidamente.

---

## 3. Fallo en cascada (Cascading Failure)

### Qué es

Un fallo en un servicio hoja se propaga hacia arriba por la cadena de
dependencias, causando fallos en todos los servicios que dependen de él.
Es el patrón de fallo más común y más difícil de diagnosticar en sistemas
distribuidos porque todos los servicios de la cadena parecen haber fallado
simultáneamente.

### Cómo se manifiesta en logs

```
Servicio B (api-inventario) — CAUSA RAÍZ:
  traceId: abc123
  event_type: SERVER_ERROR
  error_type: CannotCreateTransactionException
  duration_ms: 29014
  level: ERROR

Servicio A (api-pedidos) — VÍCTIMA:
  traceId: abc123
  event_type: UNHANDLED_ERROR
  error_type: HttpServerErrorException$InternalServerError
  error_message: "500 Internal Server Error: 'Internal error'"
  error_origin: "PedidoService.retirarStockDeInventario(PedidoService.java:57)"
  duration_ms: 5273
  level: ERROR
```

### Señales diagnósticas

- Múltiples servicios muestran errores en el mismo intervalo de tiempo.
- Los errores comparten el mismo `traceId` entre servicios.
- El campo `is_cascada` en el modelo ML tiene valor `1`.
- El `error_origin` del servicio consumidor apunta al método que realiza
  la llamada HTTP al servicio origen (`retirarStockDeInventario`, por ejemplo).

### Algoritmo de diagnóstico

1. Agrupar todos los logs del incidente por `traceId`.
2. Ordenar por `@timestamp` ascendente.
3. El primer log con `level=ERROR` en el timeline es el punto de origen.
4. El servicio con mayor `duration_ms` es el cuello de botella real.
5. Los demás errores en el mismo `traceId` son consecuencia, no causa.

---

## 4. Degradación de latencia (Latency Degradation)

### Qué es

Un servicio empieza a responder más lento de lo normal sin llegar a fallar
completamente. Las peticiones siguen completándose con HTTP 200 pero el
`duration_ms` aumenta progresivamente. Si no se detecta a tiempo, puede
derivar en timeouts y fallos en cascada.

### Cómo se manifiesta en logs

```
Logs normales (baseline):
  event_type: HTTP_REQUEST
  outcome: SUCCESS
  http_status: 200
  duration_ms: 120  ← latencia normal

Logs con degradación:
  event_type: HTTP_REQUEST
  outcome: SUCCESS
  http_status: 200
  duration_ms: 3400  ← latencia anómala pero sin error visible
```

### Señales diagnósticas

- `outcome` es `SUCCESS` y `http_status` es 200 (no hay error aparente).
- `duration_ms` es significativamente superior al baseline histórico del servicio.
- La feature `duracion_relativa` del modelo ML tiene valor superior a 3.0
  (la petición tardó más de 3 veces el tiempo normal).
- El Isolation Forest marca estas peticiones como anomalías aunque no haya error.

### Por qué es importante detectarlo

La degradación de latencia es un precursor de fallo. Un servicio que empieza
a tardar 3000ms cuando normalmente tarda 100ms está bajo presión. Si no se
actúa, el siguiente paso es que los consumidores empiecen a recibir timeouts.

---

## 5. Error de validación (Validation Error)

### Qué es

El cliente envía una petición con datos inválidos o incompletos. El servidor
rechaza la petición con HTTP 400 antes de ejecutar ninguna lógica de negocio.
No es un fallo de infraestructura.

### Cómo se manifiesta en logs

```
event_type: VALIDATION_ERROR
outcome: FAILURE
http_status: 400
error_type: MethodArgumentNotValidException
error_message: "Field 'cantidad' must be greater than 0"
duration_ms: 8  ← muy bajo, rechazado antes de tocar la BD
level: WARN
```

### Señales diagnósticas

- `http_status` es 400 o 422.
- `duration_ms` es muy bajo (< 50ms), porque el rechazo ocurre antes de
  ejecutar lógica de negocio.
- `error_type` es `MethodArgumentNotValidException` o `ConstraintViolationException`.
- No afecta a otros servicios (no hay traceId compartido con errores en otros servicios).

### Interpretación

Los errores de validación recurrentes desde la misma fuente indican un bug
en el cliente que llama a la API, no un problema en la infraestructura.
No requieren acción en el servidor.

---

## 6. Error de autenticación (Auth Error)

### Qué es

Una petición llega sin token JWT, con un token expirado o con un token
firmado con una clave incorrecta. Spring Security rechaza la petición
antes de que llegue al controller.

### Cómo se manifiesta en logs

```
event_type: AUTH_ERROR
outcome: FAILURE
http_status: 401 o 403
duration_ms: 3  ← rechazado en el filtro de seguridad
level: WARN
```

### Señales diagnósticas

- `http_status` es 401 (no autenticado) o 403 (autenticado pero sin permisos).
- `duration_ms` es extremadamente bajo (< 10ms) porque el rechazo ocurre
  en el filtro de seguridad, antes de llegar al controller.
- `event_type` es `AUTH_ERROR`.

### Patrones recurrentes de AUTH_ERROR

- Errores 401 repetidos desde el mismo cliente: el token ha expirado y el
  cliente no está renovándolo correctamente.
- Errores 403 en un endpoint específico: el usuario autenticado no tiene
  los roles necesarios para acceder a ese recurso.

---

## 7. Recurso no encontrado (Not Found)

### Qué es

El cliente solicita un recurso que no existe en la base de datos.
El servidor devuelve HTTP 404.

### Cómo se manifiesta en logs

```
event_type: NOT_FOUND
outcome: FAILURE
http_status: 404
duration_ms: 45
level: WARN
```

### Señales diagnósticas

- `http_status` es 404.
- `event_type` es `NOT_FOUND`.
- `duration_ms` es bajo pero no tan bajo como los errores de autenticación,
  porque sí llega a consultar la base de datos antes de saber que no existe.

### Patrones recurrentes de NOT_FOUND

- Peticiones DELETE o GET repetidas sobre los mismos IDs que no existen:
  indica un bug en el cliente que intenta operar sobre recursos ya eliminados.

---

## Tabla de referencia rápida

| error_type | Causa más probable | Acción |
|---|---|---|
| `CannotCreateTransactionException` | Pool de BD agotado o BD no disponible | Revisar estado de PostgreSQL y pool HikariCP |
| `ResourceAccessException` + "Read timed out" | Timeout esperando a otro servicio | Buscar mismo traceId en el servicio dependiente |
| `HttpServerErrorException$InternalServerError` | Servicio dependiente devolvió 500 | Buscar mismo traceId en el servicio origen del 500 |
| `MethodArgumentNotValidException` | Datos inválidos del cliente | No requiere acción de infraestructura |
| `NullPointerException` | Campo nulo no manejado en el código | Revisar `error_origin` para identificar la línea exacta |
| `DataIntegrityViolationException` | Violación de constraint en BD (duplicado, FK) | Revisar los datos enviados y las constraints de la tabla |
| `NoResourceFoundException` | Endpoint no existe o bloqueado por Security | Verificar la ruta y la configuración de Spring Security |
