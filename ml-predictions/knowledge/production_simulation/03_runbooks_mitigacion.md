# Runbooks de Mitigación — RCA Platform

Un runbook es un conjunto de pasos ordenados para diagnosticar y resolver
un tipo específico de incidente. Este documento cubre los escenarios de
fallo más comunes en el sistema y las acciones exactas para resolverlos.

---

## Runbook 1: Pool de conexiones de base de datos agotado

### Síntomas

- Logs con `error_type: CannotCreateTransactionException`
- `error_cause_message` menciona `HikariPool` y `Connection is not available`
- `duration_ms` cercano o superior a 30000ms en múltiples peticiones simultáneas
- El servicio afectado sigue respondiendo (no está caído), pero con errores y alta latencia

### Diagnóstico

```bash
# 1. Ver los logs recientes del servicio afectado
docker logs <nombre-contenedor> --tail 100 | grep -i "hikari\|connection\|pool"

# 2. Verificar el estado de la BD
docker exec -it <contenedor-postgres> psql -U <usuario> -d <base_de_datos> \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# 3. Ver conexiones activas en detalle
docker exec -it <contenedor-postgres> psql -U <usuario> -d <base_de_datos> \
  -c "SELECT pid, state, wait_event_type, wait_event, query_start, query \
      FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"
```

### Resolución

```bash
# Opción A: Terminar conexiones bloqueadas en PostgreSQL
docker exec -it <contenedor-postgres> psql -U <usuario> -d <base_de_datos> \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity \
      WHERE state = 'idle in transaction' AND query_start < now() - interval '5 minutes';"

# Opción B: Reiniciar el microservicio (libera el pool de HikariCP)
docker compose restart <nombre-servicio>

# Opción C: Reiniciar solo el contenedor de la BD (más agresivo)
docker compose restart <nombre-servicio-postgres>
```

### Prevención a largo plazo

- Configurar `spring.datasource.hikari.maximum-pool-size` según la carga esperada.
- Configurar `spring.datasource.hikari.connection-timeout` a un valor menor al
  timeout de los servicios consumidores para fallar rápido.
- Añadir índices a las columnas más consultadas para reducir el tiempo de query.
- Revisar transacciones largas o consultas sin índice con `EXPLAIN ANALYZE`.

---

## Runbook 2: Servicio no disponible (contenedor caído)

### Síntomas

- Logs en el servicio consumidor con `error_type: ResourceAccessException`
  y `error_message: "Connection refused"` (diferente a timeout)
- El servicio dependiente no aparece en `docker compose ps` como `Up`
- Todos los endpoints del servicio consumidor que dependen del servicio caído
  devuelven HTTP 500

### Diagnóstico

```bash
# 1. Ver el estado de todos los contenedores
docker compose ps

# 2. Ver los últimos logs del contenedor caído antes de morir
docker logs <nombre-contenedor> --tail 200

# 3. Ver si el contenedor está en estado de reinicio continuo
docker inspect <nombre-contenedor> | grep -A5 "RestartCount\|Status\|ExitCode"
```

### Resolución

```bash
# Reiniciar el servicio caído
docker compose start <nombre-servicio>

# Si el contenedor está en bucle de reinicio, reconstruir la imagen
docker compose up -d --build <nombre-servicio>

# Ver logs en tiempo real tras el reinicio para verificar que arranca
docker logs -f <nombre-servicio>
```

### Diferencia clave entre "caído" y "lento"

| Señal | Servicio caído | Servicio lento |
|---|---|---|
| `error_message` | "Connection refused" | "Read timed out" |
| `duration_ms` | < 100ms (falla inmediatamente) | ~ 5000ms (espera el timeout) |
| `docker compose ps` | `Exit` o `Restarting` | `Up` |

---

## Runbook 3: Degradación de latencia progresiva

### Síntomas

- Peticiones que completan con HTTP 200 pero `duration_ms` aumenta progresivamente.
- El modelo ML marca peticiones como anomalías aunque `outcome` sea `SUCCESS`.
- `duracion_relativa` superior a 3.0 en múltiples peticiones consecutivas del mismo servicio.

### Diagnóstico

```bash
# 1. Ver el consumo de recursos del contenedor
docker stats <nombre-contenedor> --no-stream

# 2. Buscar queries lentas en PostgreSQL
docker exec -it <contenedor-postgres> psql -U <usuario> -d <base_de_datos> \
  -c "SELECT query, calls, mean_exec_time, max_exec_time \
      FROM pg_stat_statements \
      ORDER BY mean_exec_time DESC LIMIT 10;"

# 3. Ver el estado del pool de HikariCP via Actuator
curl http://localhost:<puerto>/actuator/metrics/hikaricp.connections.active
curl http://localhost:<puerto>/actuator/metrics/hikaricp.connections.pending
```

### Interpretación de métricas HikariCP

- `hikaricp.connections.active` cercano a `maximum-pool-size`: el pool está bajo presión.
- `hikaricp.connections.pending` > 0: hay peticiones esperando conexión disponible.
- Si ambas métricas aumentan progresivamente, es un precursor de `CannotCreateTransactionException`.

### Resolución

```bash
# Aumentar el pool temporalmente (requiere reinicio)
# En application.properties:
# spring.datasource.hikari.maximum-pool-size=20

# Identificar y optimizar la query más lenta
docker exec -it <contenedor-postgres> psql -U <usuario> -d <base_de_datos> \
  -c "EXPLAIN ANALYZE <query-lenta>;"

# Forzar recolección de estadísticas de PostgreSQL
docker exec -it <contenedor-postgres> psql -U <usuario> -d <base_de_datos> \
  -c "ANALYZE;"
```

---

## Runbook 4: Errores 401/403 recurrentes

### Síntomas

- `event_type: AUTH_ERROR` aparece con frecuencia desde la misma fuente.
- `http_status: 401` indica token ausente o expirado.
- `http_status: 403` indica token válido pero sin permisos para ese recurso.

### Diagnóstico

```bash
# Ver la configuración de expiración del JWT
# En application.properties del servicio de autenticación:
# jwt.expiration=86400000  (24 horas en milisegundos)

# Si el tiempo de expiración es muy corto, los clientes reciben 401 frecuentemente
```

### Resolución para 401 (token expirado)

- El cliente debe renovar el token antes de que expire.
- Verificar que el tiempo de expiración del JWT es adecuado para el caso de uso.
- Implementar lógica de refresh token en el cliente si el token expira durante
  sesiones largas.

### Resolución para 403 (sin permisos)

- Verificar que el usuario tiene los roles necesarios en la base de datos de autenticación.
- Revisar la configuración de `SecurityFilterChain` en el servicio que devuelve 403
  para asegurarse de que los endpoints tienen los permisos correctos.

---

## Runbook 5: Error de integridad de datos (DataIntegrityViolationException)

### Síntomas

- `error_type: DataIntegrityViolationException`
- `error_message` menciona `duplicate key`, `foreign key constraint` o `not-null constraint`
- El error ocurre en operaciones de escritura (POST, PUT, DELETE)

### Causas comunes y resolución

**Clave duplicada (duplicate key):**
```sql
-- Verificar qué registro ya existe
SELECT * FROM <tabla> WHERE <campo_unique> = '<valor>';
```

**Violación de clave foránea (foreign key constraint):**
```sql
-- Verificar que el registro padre existe antes de crear el hijo
SELECT * FROM <tabla_padre> WHERE id = <id_referenciado>;
```

**Campo no nulo (not-null constraint):**
- El cliente está enviando un campo nulo que la BD no acepta.
- Añadir validación `@NotNull` en el DTO del servicio para rechazar antes de llegar a la BD.

---

## Runbook 6: Diagnóstico de fallo en cascada via traceId

### Cuándo usar este runbook

Cuando múltiples servicios muestran errores en el mismo intervalo de tiempo
y se sospecha que están relacionados.

### Procedimiento

```bash
# 1. Identificar el traceId del incidente desde Grafana o Loki
# Ir a Grafana → Explore → Loki
# Query: {level="ERROR"} | json | duration_ms > 1000

# 2. Una vez identificado el traceId, buscar todos los logs de ese trace
# Query en Loki:
# {service=~"api-.*"} | json | traceId="<el-trace-id>"

# 3. Ordenar los resultados por timestamp ascendente

# 4. El primer log con level=ERROR es el punto de inicio del fallo
# El servicio con mayor duration_ms es el cuello de botella real
```

### Interpretación del resultado

```
Timeline del traceId abc123 (ordenado por timestamp):

08:05:35.000  api-inventario  SERVER_ERROR      duration_ms=29014  ← CAUSA RAÍZ
08:05:35.850  api-pedidos     UNHANDLED_ERROR   duration_ms=5273   ← SÍNTOMA

Conclusión:
- api-inventario falló primero (timestamp más temprano)
- api-inventario tiene el duration_ms más alto (29014ms)
- api-pedidos simplemente recibió el error de api-inventario y lo propagó
- La acción correcta es investigar api-inventario, no api-pedidos
```

---

## Referencia de comandos Docker útiles

```bash
# Ver estado de todos los servicios
docker compose ps

# Ver logs de un servicio en tiempo real
docker logs -f <nombre-servicio>

# Ver logs de un servicio con filtro
docker logs <nombre-servicio> 2>&1 | grep -i "error\|exception"

# Reiniciar un servicio sin reconstruir
docker compose restart <nombre-servicio>

# Reiniciar un servicio reconstruyendo la imagen
docker compose up -d --build <nombre-servicio>

# Ver el consumo de recursos de todos los contenedores
docker stats --no-stream

# Entrar a un contenedor para diagnóstico
docker exec -it <nombre-contenedor> sh

# Ver las métricas de Actuator de Spring Boot
curl http://localhost:<puerto>/actuator/health
curl http://localhost:<puerto>/actuator/metrics
```
