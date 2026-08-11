# Arquitectura y Topología del Sistema — RCA Platform

## Descripción general

RCA Platform es un sistema de microservicios orientado al comercio electrónico
compuesto por tres servicios backend independientes, cada uno con su propia base
de datos dedicada (patrón Database per Service). Los servicios se comunican entre
sí de forma síncrona mediante HTTP REST.

El sistema implementa trazabilidad distribuida mediante Micrometer Tracing con
Brave (OpenZipkin). Cada petición HTTP recibe un identificador único (`traceId`)
que se propaga automáticamente en las cabeceras HTTP (formato B3) entre todos los
servicios involucrados en el procesamiento de esa petición.

---

## Servicios y sus responsabilidades

### api-autenticacion

Servidor de identidad y autorización del sistema.

- Gestiona el ciclo de vida de los usuarios: registro, autenticación y emisión de credenciales.
- Emite tokens JWT firmados con algoritmo HS256 con tiempo de expiración configurable.
- Las contraseñas se almacenan usando BCrypt con salt aleatorio.
- Es un servicio hoja: no realiza llamadas HTTP a ningún otro microservicio.
- Toda petición a api-inventario o api-pedidos debe incluir un token JWT válido
  en la cabecera `Authorization: Bearer <token>`.
- Tiempo de respuesta esperado: inferior a 200ms en condiciones normales.
  Valores superiores a 500ms indican contención en la base de datos o
  sobrecarga de CPU por el coste computacional de BCrypt.

### api-inventario

Resource Server responsable del catálogo de productos y la gestión de stock.

- Mantiene el registro de productos disponibles y sus cantidades en stock.
- Expone operaciones CRUD sobre productos y una operación de reserva de stock.
- La operación de reserva (`POST /inventario/{id}/retirar`) es el punto de
  integración crítico con api-pedidos. Es una operación de escritura que
  modifica el stock disponible y requiere transacción de base de datos.
- Es un servicio hoja: no realiza llamadas HTTP a ningún otro microservicio.
- Tiempo de respuesta esperado: inferior a 150ms para lecturas,
  inferior a 300ms para escrituras en condiciones normales.
- La operación de retirada de stock puede generar contención cuando múltiples
  pedidos intentan reservar el mismo producto simultáneamente, produciendo
  bloqueos a nivel de fila en PostgreSQL.

### api-pedidos

Resource Server orquestador. Es el único servicio que realiza llamadas HTTP
a otros servicios del sistema.

- Gestiona el ciclo de vida de los pedidos: creación, consulta y estado.
- La creación de un pedido es una operación compuesta que involucra dos sistemas:
  1. Llama a api-inventario para reservar el stock del producto solicitado.
  2. Si la reserva es exitosa, persiste el pedido en su propia base de datos.
  3. Si la reserva falla, el pedido no se crea y el error se propaga al cliente.
- El timeout configurado para las llamadas a api-inventario es de 5000ms.
  Si api-inventario no responde en ese tiempo, api-pedidos lanza una excepción
  de tipo `ResourceAccessException` y devuelve HTTP 500 al cliente.
- Tiempo de respuesta esperado: inferior a 500ms en condiciones normales.
  Este tiempo incluye la llamada HTTP síncrona a api-inventario.

---

## Diagrama de dependencias

```
Cliente (externo)
        │
        ├──► POST /api/auth/login ──► api-autenticacion ──► postgres-autenticacion
        │
        ├──► GET/POST /inventario ──► api-inventario ──► postgres-inventario
        │
        └──► POST /pedidos ──────────► api-pedidos ──────► postgres-pedidos
                                              │
                                              └──► POST /inventario/{id}/retirar
                                                          │
                                                          ▼
                                                   api-inventario ──► postgres-inventario
```

La única dependencia entre servicios en tiempo de ejecución es:
**api-pedidos → api-inventario**

Esta dependencia es síncrona y bloqueante. Si api-inventario no está disponible
o responde con error, api-pedidos no puede completar la creación de pedidos.

---

## Propagación del traceId y diagnóstico de fallos en cascada

Cuando api-pedidos llama a api-inventario, el traceId se propaga automáticamente
en la cabecera HTTP `X-B3-TraceId`. Esto significa que ambos servicios registran
logs con el mismo identificador para la misma operación de negocio.

Este mecanismo es la base del diagnóstico de fallos en cascada:

```
Ejemplo de fallo en cascada (mismo traceId: abc123):

Log en api-inventario:
  traceId: abc123
  service: api-inventario
  event_type: SERVER_ERROR
  duration_ms: 29014        ← latencia anormalmente alta
  level: ERROR

Log en api-pedidos:
  traceId: abc123
  service: api-pedidos
  event_type: UNHANDLED_ERROR
  error_type: ResourceAccessException
  error_message: "Read timed out"
  duration_ms: 5273
  level: ERROR
```

**Regla fundamental de diagnóstico:**
El servicio con el `duration_ms` más alto y el timestamp de inicio más temprano
dentro del mismo `traceId` es la causa raíz del incidente.
Los demás servicios que muestran errores con el mismo `traceId` son víctimas
del efecto cascada, no causas independientes.

---

## Base de datos por servicio

Cada microservicio tiene su propia instancia de PostgreSQL aislada.
Ningún servicio accede directamente a la base de datos de otro servicio.

| Servicio | Base de datos | Puerto externo |
|---|---|---|
| api-autenticacion | postgres-autenticacion | 5434 |
| api-inventario | postgres-inventario | 5432 |
| api-pedidos | postgres-pedidos | 5433 |

La comunicación entre servicios se realiza exclusivamente a través de las APIs
HTTP expuestas. No existe acceso cruzado a bases de datos.

---

## Orquestación

El sistema se despliega mediante Docker Compose. Todos los servicios comparten
la red interna `rca-net` y se comunican usando los nombres de los contenedores
como hostnames (ej: `http://api-inventario:8080`).

El stack de observabilidad (Promtail, Loki, Grafana) también corre en la misma
red y recoge los logs de todos los servicios mediante el socket de Docker.
