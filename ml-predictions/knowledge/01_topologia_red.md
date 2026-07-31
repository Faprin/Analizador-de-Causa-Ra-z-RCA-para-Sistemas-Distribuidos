# Topología de Red — RCA Platform

## Visión general

El sistema está compuesto por tres microservicios desplegados en Docker Compose
bajo la red interna `rca-net`. Cada servicio tiene su propia base de datos
PostgreSQL dedicada (patrón Database per Service).

```
Cliente externo
      │
      ▼
api-autenticacion (puerto 8082)
      │ emite JWT
      ▼
api-pedidos (puerto 8081) ──────────────► api-inventario (puerto 8080)
      │                                         │
      ▼                                         ▼
postgres-pedidos (5433)              postgres-inventario (5432)

api-autenticacion
      │
      ▼
postgres-autenticacion (5434)
```

---

## Microservicio: api-autenticacion

- **Puerto interno Docker:** 8082
- **Base de datos:** postgres-autenticacion en puerto 5434
- **Responsabilidad:** Registro de usuarios, login, emisión de tokens JWT (HS256).
- **Endpoints principales:**
  - `POST /api/auth/register` — registro de nuevo usuario
  - `POST /api/auth/login` — autenticación y emisión de JWT
- **No llama a ningún otro microservicio.** Es un servicio hoja.
- **Tiempo de respuesta normal:** < 200ms (operaciones de BCrypt + JWT)
- **Señal de fallo:** Si supera 500ms es síntoma de saturación de BD o CPU alta por BCrypt.

---

## Microservicio: api-inventario

- **Puerto interno Docker:** 8080
- **Base de datos:** postgres-inventario en puerto 5432
- **Responsabilidad:** Catálogo de productos y gestión de stock.
- **Endpoints principales:**
  - `GET /inventario` — lista todos los productos
  - `GET /inventario/{id}` — detalle de un producto
  - `POST /inventario` — crear producto
  - `DELETE /inventario/{id}` — eliminar producto
  - `POST /inventario/{id}/retirar?cantidad=N` — reserva de stock (llamado por api-pedidos)
- **No llama a ningún otro microservicio.** Es un servicio hoja.
- **Tiempo de respuesta normal:** < 150ms para lecturas, < 300ms para escrituras
- **Señal de fallo:** Si `POST /inventario/{id}/retirar` supera 1000ms, es síntoma
  de contención en la BD (bloqueos de fila por stock concurrente o pool saturado).

### Endpoints de Chaos Engineering (solo entorno de desarrollo)
- `POST /chaos/db-saturate?segundos=N` — agota el pool de conexiones de PostgreSQL
- `POST /chaos/error?type=npe` — lanza NullPointerException controlada
- `POST /chaos/error?type=db` — lanza RuntimeException simulando error de BD
- `POST /chaos/error?type=timeout` — lanza RuntimeException simulando timeout

---

## Microservicio: api-pedidos

- **Puerto interno Docker:** 8081
- **Base de datos:** postgres-pedidos en puerto 5433
- **Responsabilidad:** Orquestación de pedidos. Es el único servicio que llama a otros.
- **Endpoints principales:**
  - `GET /pedidos` — lista todos los pedidos
  - `POST /pedidos` — crea un pedido (flujo completo con reserva de stock)
- **Llama a:** `api-inventario` vía HTTP síncrono usando RestClient.
- **Flujo de creación de pedido:**
  1. Recibe `POST /pedidos` con `{clienteId, productoId, cantidad, precioUnitario}`
  2. Llama a `POST http://api-inventario:8080/inventario/{productoId}/retirar?cantidad=N`
  3. Si api-inventario responde 200 → persiste el pedido en postgres-pedidos
  4. Si api-inventario responde 500 → lanza excepción, el pedido no se crea
- **Timeout configurado hacia api-inventario:** 5000ms (5 segundos)
- **Tiempo de respuesta normal:** < 500ms (incluye la llamada HTTP a inventario)
- **Señal de fallo:** Si `POST /pedidos` supera 5000ms y devuelve 500,
  la causa raíz está en api-inventario, no en api-pedidos.

---

## Propagación del traceId

Micrometer Tracing con Brave propaga automáticamente el `traceId` en las
cabeceras HTTP (formato B3) cuando api-pedidos llama a api-inventario.

Esto significa que un fallo en cascada genera logs con el **mismo traceId**
en ambos servicios:

```
traceId: 6a44c3c1...
  api-pedidos    → UNHANDLED_ERROR  duration_ms=5273   ← síntoma
  api-inventario → SERVER_ERROR     duration_ms=29014  ← causa raíz
```

**Regla de diagnóstico:** El servicio con el `duration_ms` más alto y el
evento más temprano en el timeline es la causa raíz. El resto son víctimas
del efecto cascada.

---

## Reglas de timeout y comportamiento bajo fallo

| Escenario | Síntoma en api-pedidos | Causa probable |
|---|---|---|
| api-inventario tarda > 5000ms | `ResourceAccessException: Read timed out` | Pool BD saturado en inventario |
| api-inventario devuelve 500 | `HttpServerErrorException$InternalServerError` | Error interno en inventario |
| postgres-pedidos no disponible | `CannotCreateTransactionException` | BD de pedidos caída |
| JWT expirado | `403 Forbidden` en cualquier servicio | Token caducado, renovar JWT |
