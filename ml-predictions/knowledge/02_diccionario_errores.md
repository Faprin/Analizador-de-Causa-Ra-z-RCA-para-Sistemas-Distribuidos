# Diccionario de Errores — RCA Platform

Este documento mapea las excepciones y patrones de error del sistema
a sus causas reales y el servicio origen. Está diseñado para que el
modelo de lenguaje pueda diagnosticar incidentes a partir de los logs.

---

## Formato de un log de error

Cada error genera dos logs vinculados por el mismo `traceId`:

**Log del ErrorLoggingAdvice** (diagnóstico de la excepción):
```json
{
  "level": "ERROR",
  "service": "api-pedidos",
  "traceId": "6a44c3c1...",
  "event_type": "UNHANDLED_ERROR",
  "error_type": "ResourceAccessException",
  "error_message": "Read timed out connecting to api-inventario",
  "error_origin": "PedidoService.retirarStockDeInventario(PedidoService.java:57)"
}
```

**Log del RequestLoggingFilter** (contexto HTTP):
```json
{
  "level": "ERROR",
  "service": "api-pedidos",
  "traceId": "6a44c3c1...",
  "event_type": "SERVER_ERROR",
  "http_method": "POST",
  "http_uri": "/pedidos",
  "http_status": "500",
  "duration_ms": "5273"
}
```

---

## Catálogo de Excepciones

### ResourceAccessException + "Read timed out"

- **Servicio afectado:** api-pedidos
- **Causa raíz:** api-inventario no responde en menos de 5000ms
- **Por qué ocurre:** El pool de conexiones de postgres-inventario está saturado
o la BD está bajo
  alta carga de escritura concurrente.
- **Patrón en logs:** Mismo `traceId` en api-pedidos (timeout) y en api-inventario
  (`duration_ms` > 29000ms, `event_type: SERVER_ERROR`)
- **Servicio a inspeccionar primero:** api-inventario, no api-pedidos
- **Mitigación:** Ver Runbook `03_runbooks.md` → Sección "Pool de conexiones saturado"

---

### CannotCreateTransactionException + "could not open JPA EntityManager"

- **Servicio afectado:** Cualquiera (api-pedidos, api-inventario, api-autenticacion)
- **Causa raíz:** La base de datos PostgreSQL del servicio no está disponible
  o el pool de conexiones HikariCP está completamente agotado.
- **Patrón en logs:** `error_origin` apunta a una clase de repositorio o servicio
  que intenta hacer una query. `duration_ms` suele ser muy alto (> 30000ms).
- **Servicio a inspeccionar primero:** El propio servicio que lanza la excepción.
- **Mitigación:** Ver Runbook `03_runbooks.md` → Sección "Pool de conexiones saturado"

---

### HttpServerErrorException$InternalServerError + "500 Internal Server Error"

- **Servicio afectado:** api-pedidos (quien recibe el error de otro servicio)
- **Causa raíz:** api-inventario devolvió un HTTP 500 al intentar retirar stock.
- **Por qué ocurre:** Error interno en api-inventario — puede ser BD saturada,
  stock insuficiente no manejado, o excepción no capturada.
- **Patrón en logs:** `error_origin` apunta a `PedidoService.retirarStockDeInventario`.
  Buscar el mismo `traceId` en los logs de api-inventario para ver la causa exacta.
- **Servicio a inspeccionar primero:** api-inventario (buscar el traceId allí)
- **Mitigación:** Ver Runbook `03_runbooks.md` → Sección "Error 500 en inventario"

---

### NullPointerException

- **Servicio afectado:** api-inventario (generalmente)
- **Causa raíz en producción:** Campo nulo no validado, generalmente un producto
  con campos opcionales mal gestionados o una respuesta de BD inesperada.
- **Patrón en logs:** `error_type: NullPointerException`, `error_origin` muestra
  la línea exacta del código donde ocurre.
- **Mitigación:** Revisar la línea indicada en `error_origin`.

---

### NoResourceFoundException + "No static resource"

- **Servicio afectado:** Cualquiera
- **Causa raíz:** El endpoint solicitado no existe en el microservicio, o Spring
  Security está bloqueando la ruta antes de que llegue al controller.
- **Patrón en logs:** `http_status: 404`, `event_type: NOT_FOUND`
- **Mitigación:** Verificar que la ruta existe en el controller y que Spring Security
  permite el acceso (`requestMatchers("/ruta/**").permitAll()`).

---

### MethodArgumentNotValidException

- **Servicio afectado:** Cualquiera
- **Causa raíz:** El cliente envió un body JSON con campos inválidos o faltantes.
- **Patrón en logs:** `event_type: VALIDATION_ERROR`, `http_status: 400`,
  `error_message` contiene el campo que falló y la constraint violada.
- **Es un error del cliente, no del servidor.** No requiere acción en la infraestructura.

---

## Patrones de fallo en cascada

### Patrón 1: Saturación de BD → Timeout en cascada

```
Secuencia de eventos (mismo traceId):

T+1000ms api-pedidos recibe POST /pedidos
T+1000ms api-pedidos llama a api-inventario → espera respuesta
T+6000ms api-pedidos lanza ResourceAccessException (timeout 5000ms)
T+6000ms api-pedidos devuelve HTTP 500 al cliente

Logs resultantes:
  api-inventario → duration_ms: 29014, event_type: SERVER_ERROR  ← CAUSA RAÍZ
  api-pedidos    → duration_ms: 5273,  event_type: UNHANDLED_ERROR ← SÍNTOMA
```

**Diagnóstico:** La causa raíz es api-inventario. El `duration_ms` anormalmente
alto (29014ms) en inventario confirma que la BD estaba bloqueada.

---

### Patrón 2: Error controlado → 500 en cascada

```
Secuencia de eventos (mismo traceId):

T+0ms   api-inventario lanza RuntimeException → devuelve HTTP 500
T+1ms   api-pedidos recibe POST /pedidos
T+1ms   api-pedidos llama a api-inventario → recibe HTTP 500
T+2ms   api-pedidos lanza HttpServerErrorException → devuelve HTTP 500

Logs resultantes:
  api-inventario → event_type: SERVER_ERROR, error_type: RuntimeException ← CAUSA RAÍZ
  api-pedidos    → event_type: UNHANDLED_ERROR, error_type: InternalServerError ← SÍNTOMA
```

---

## Reglas de diagnóstico para el modelo

1. **El servicio con mayor `duration_ms` en el mismo `traceId` es el cuello de botella.**
2. **El servicio con el timestamp más temprano en el mismo `traceId` es la causa raíz.**
3. **Si `error_origin` apunta a `PedidoService.retirarStockDeInventario`, busca el traceId en api-inventario.**
4. **`CannotCreateTransactionException` siempre significa problema de BD, no de lógica.**
5. **`is_cascada=1` en el modelo ML indica que el mismo traceId tiene ERROR en más de un servicio.**
6. **Un `duration_ms` > 5000ms en api-pedidos casi siempre es timeout esperando a api-inventario.**
