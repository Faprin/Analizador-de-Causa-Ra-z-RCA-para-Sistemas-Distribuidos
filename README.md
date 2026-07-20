# 🔍 RCA Platform — Analizador de Causa Raíz para Sistemas Distribuidos

Plataforma de **observabilidad inteligente** que combina ingeniería del caos, trazabilidad distribuida y Machine Learning no supervisado para identificar automáticamente la causa raíz de fallos en cascada en arquitecturas de microservicios.

> **Estado actual:** Fase 3 completada — Motor analítico FastAPI + Isolation Forest operativo.

---

## 🎯 El Problema que Resuelve

En arquitecturas de microservicios, un fallo en un único nodo genera un efecto dominó que produce cientos de excepciones en servicios interdependientes. Aislar el origen exacto del fallo requiere horas de análisis manual. Esta plataforma reduce ese tiempo **de horas a segundos**.

---

## 🏗️ Arquitectura

El sistema se divide en tres capas:

```
┌─────────────────────────────────────────────────────┐
│          Capa de Simulación (Java / Spring Boot)     │
│   api-autenticacion │ api-inventario │ api-pedidos   │
│   Logs JSON + TraceId distribuido + Chaos endpoints  │
└─────────────────────┬───────────────────────────────┘
                      │ stdout JSON
┌─────────────────────▼───────────────────────────────┐
│           Stack PLG (Promtail + Loki + Grafana)      │
│   Recolección → Indexación → Visualización en tiempo │
└─────────────────────┬───────────────────────────────┘
                      │ API Loki
┌─────────────────────▼───────────────────────────────┐
│             Capa Analítica (Python / FastAPI)         │
│   features.py → Isolation Forest + TF-IDF NLP        │
│   /predict  /analize  /health                        │
└─────────────────────────────────────────────────────┘
```

### Patrón de trazabilidad distribuida

Cada petición HTTP recibe un `traceId` único que se propaga automáticamente entre microservicios mediante Micrometer Tracing (Brave). Un fallo en cascada queda vinculado en los logs de todos los servicios implicados por el mismo identificador:

```json
{ "traceId": "6a44c3c1...", "service": "api-pedidos",    "event_type": "UNHANDLED_ERROR", "duration_ms": 5273  }
{ "traceId": "6a44c3c1...", "service": "api-inventario", "event_type": "SERVER_ERROR",    "duration_ms": 29014 }
```

---

## 📦 Microservicios

### 🛡️ api-autenticacion `puerto 8082`
Servidor de identidad y autorización. Gestiona el registro de usuarios, encriptación de contraseñas con BCrypt y emisión de tokens JWT.

### 📦 api-inventario `puerto 8080`
Resource Server. Gestiona el catálogo de productos y el stock disponible. Incluye endpoints de Chaos Engineering para inyección controlada de fallos.

### 🛒 api-pedidos `puerto 8081`
Resource Server. Orquesta la creación de pedidos comunicándose síncronamente con Inventario para la reserva de stock. Propaga el `traceId` en todas las llamadas HTTP salientes.

### 🤖 ml-predictions `puerto 8000`
Motor analítico Python con FastAPI. Descarga logs desde Loki, los transforma con un pipeline de features, vectoriza los mensajes de error con TF-IDF y aplica Isolation Forest para detectar anomalías y aislar la causa raíz.

---

## 🧱 Paquete `observability`

Cada microservicio Spring Boot implementa el mismo paquete de observabilidad:

```
src/main/java/rca/{servicio}/observability/
├── RequestLoggingFilter.java   # Registra método, URI, status, duration_ms y event_type via MDC
├── ErrorLoggingAdvice.java     # Captura excepciones con tipo exacto y error_origin limpio
└── ChaosController.java        # Endpoints de inyección de fallos controlada
```

Todos los logs se emiten como JSON estructurado con campos indexables por Loki:

| Campo | Descripción |
|---|---|
| `traceId` | Vincula todos los logs de una misma petición entre servicios |
| `event_type` | `HTTP_REQUEST` `VALIDATION_ERROR` `AUTH_ERROR` `SERVER_ERROR` `UNHANDLED_ERROR` |
| `outcome` | `SUCCESS` o `FAILURE` |
| `duration_ms` | Latencia total — feature clave para detectar degradación |
| `error_origin` | Frames del stack trace filtrados al código propio (máx. 3 frames) |
| `error_type` | Nombre exacto de la excepción |

---

## ⚡ Chaos Engineering

Cada microservicio expone endpoints de inyección de fallos para generar datos de entrenamiento anómalos:

```bash
# Satura el pool de conexiones de PostgreSQL (afecta a todas las peticiones)
POST /chaos/db-saturate?segundos=8

# Inyecta una excepción controlada
POST /chaos/error?type=npe
POST /chaos/error?type=db
POST /chaos/error?type=timeout
```

El script `ml-predictions/dataset_generator.py` automatiza la generación del dataset mezclando tráfico normal (60%), errores simples (20%) y fallos en cascada (20%).

---

## 🤖 Motor Analítico (ml-predictions)

### Pipeline de transformación (`features.py`)

Los logs crudos de Loki pasan por un pipeline de transformación antes de llegar al modelo:

```
logs crudos
    │
    ▼
fill_na()          # rellena nulos con valores por defecto
    │
    ▼
logs_unifier()     # agrupa logs por traceId + service, calcula log_count
    │
    ▼
text_builder()     # construye texto_completo para TF-IDF
    │
    ▼
features_generator() # genera tiene_error_5xx, duracion_relativa, is_cascada
    │
    ▼
col_remover()      # elimina columnas que no entran al modelo
```

### Features del modelo

| Feature | Tipo | Descripción |
|---|---|---|
| `event_type` | Categórica (OneHot) | Tipo de evento HTTP |
| `http_method` | Categórica (OneHot) | Verbo HTTP |
| `http_status` | Categórica (OneHot) | Código de respuesta |
| `duration_ms` | Numérica (RobustScaler) | Latencia total de la petición |
| `duracion_relativa` | Numérica (RobustScaler) | Ratio vs baseline normal del servicio |
| `level` | Ordinal (INFO=0, WARN=1, ERROR=2) | Severidad del log |
| `log_count` | Numérica | Número de logs agrupados en el mismo traceId |
| `tiene_error_5xx` | Binaria (passthrough) | Si hay error 5xx en la petición |
| `is_cascada` | Binaria (passthrough) | Si el traceId aparece con ERROR en más de un servicio |
| `texto_completo` | TF-IDF (NLP) | Vectorización de error_type + error_message + error_origin |

### Endpoints FastAPI

| Endpoint | Método | Descripción |
|---|---|---|
| `/health` | GET | Estado del servidor y del modelo |
| `/predict` | POST | Recibe logs en JSON y devuelve anomalías detectadas |
| `/analize` | GET | Descarga logs de Loki automáticamente y devuelve anomalías |

### Estructura del motor analítico

```
ml-predictions/
├── src/
│   ├── main.py          # FastAPI — endpoints y lifespan
│   ├── model.py         # Wrapper del modelo pkl
│   └── features.py      # Pipeline de transformación de logs
├── modelos/
│   ├── isolation_forest.pkl   # Modelo entrenado
│   ├── baseline.pkl           # Baseline de latencia por servicio
│   └── metadatos.json         # Parámetros y fecha de entrenamiento
├── notebooks/
│   └── 01_Isolation_TF-IDF.ipynb  # Notebook de entrenamiento
├── datasets/
│   ├── 01_logs_dataset.csv
│   └── 02_logs_dataset.csv
└── dataset_generator.py   # Generador de tráfico para entrenamiento
```

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Java 21, Spring Boot 3.4.6 |
| Seguridad | Spring Security, JWT (jjwt 0.11.5), BCrypt |
| Persistencia | Spring Data JPA, PostgreSQL 15 |
| Trazabilidad | Micrometer Tracing, Brave, Logstash Logback Encoder |
| Observabilidad | Promtail, Loki 2.9.2, Grafana 10 |
| Motor analítico | Python 3.11, FastAPI, Scikit-Learn, Pandas, Joblib |
| ML | Isolation Forest, TF-IDF, RobustScaler, OrdinalEncoder, OneHotEncoder |
| Orquestación | Docker, Docker Compose |

---

## 📂 Estructura del Repositorio

```
/
├── api-autenticacion/        # Servicio de identidad y JWT
│   └── src/.../observability/
├── api-inventario/           # Gestión de stock
│   └── src/.../observability/
├── api-pedidos/              # Gestión de órdenes
│   └── src/.../observability/
├── ml-predictions/           # Motor analítico Python
│   ├── src/
│   │   ├── main.py           # FastAPI
│   │   ├── model.py          # Wrapper del modelo
│   │   └── features.py       # Pipeline de transformación
│   ├── modelos/              # Modelo pkl + metadatos
│   ├── notebooks/            # Notebooks de entrenamiento
│   ├── datasets/             # Dataset exportado desde Loki
│   └── dataset_generator.py  # Generador de tráfico
├── docker-compose.yml        # Orquestación completa del entorno
├── loki-config.yaml          # Configuración de Loki (schema v12, tsdb)
├── promtail-config.yaml      # Scraping de logs via Docker socket
└── .gitignore
```

---

## 🚀 Arranque del Entorno

```bash
# Construir y levantar todos los servicios
docker compose up -d --build

# Verificar que todos los contenedores están activos
docker compose ps

# Comprobar que Loki está listo
curl http://localhost:3100/ready

# Acceder a Grafana
open http://localhost:3000
```

### Arrancar el motor analítico

```bash
cd ml-predictions/src
uvicorn main:app --reload

# Comprobar que el modelo está cargado
curl http://localhost:8000/health

# Analizar la última hora de logs automáticamente
curl http://localhost:8000/analize?horas=1
```

### Generar dataset de entrenamiento

```bash
cd ml-predictions
pip install requests
python dataset_generator.py
```

---

## 📊 Fases del Proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 1 — Infraestructura | Microservicios Spring Boot con logs estructurados y trazabilidad distribuida | ✅ Completada |
| 2 — Chaos Engineering | Inyección de fallos, stack PLG y generación del dataset | ✅ Completada |
| 3 — Motor Analítico | FastAPI + Isolation Forest + TF-IDF para detección de anomalías | ✅ Completada |
| 4 — Visualización | Panel Angular/Astro con alertas en tiempo real | 🔄 En desarrollo |
| 5 — GenAI / RAG | Informes post-mortem automáticos con LLM | 📋 Planificado |
