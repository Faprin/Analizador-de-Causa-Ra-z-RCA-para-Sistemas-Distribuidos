# 🚀 Analizador de Causa Raíz (RCA) para Sistemas Distribuidos

Este repositorio contiene una arquitectura de microservicios orientada a eventos, diseñada con principios de **Zero Trust Security** y un enfoque de despliegue en contenedores. El sistema gestiona un flujo de comercio electrónico (autenticación, inventario y pedidos) y está preparado para integrar un módulo de Inteligencia Artificial para la predicción de riesgo de incendios en España.

## 🏗️ Arquitectura del Sistema

El proyecto sigue el patrón **Database per Service** (Base de datos por servicio) para garantizar la escalabilidad y tolerancia a fallos. La comunicación entre microservicios se realiza mediante clientes HTTP REST (`RestClient`) implementando propagación de tokens JWT (Token Relay).

### 📦 Módulos Actuales

* **🛡️ API Autenticación:** Actúa como el servidor de autorización. Gestiona el registro de usuarios, contraseñas encriptadas con BCrypt y la emisión de tokens JWT.
* **📦 API Inventario:** Resource Server. Gestiona el catálogo de productos y el stock disponible. Validado por JWT.
* **🛒 API Pedidos:** Resource Server. Orquesta la creación de pedidos comunicándose de forma síncrona con el Inventario para la reserva de stock. Validado por JWT.
* **🔥 ML Predicción (Próximamente):** Módulo de Inteligencia Artificial desarrollado en Python para evaluar el riesgo de incendios utilizando datos meteorológicos históricos.

## 🛠️ Tecnologías Utilizadas

* **Backend:** Java 21, Spring Boot 3, Spring Security, Spring Data JPA
* **Seguridad:** JWT (JSON Web Tokens), BCrypt
* **Base de Datos:** PostgreSQL (Bases de datos independientes por servicio)
* **Despliegue & Orquestación:** Docker, Docker Compose
* **IA / Data Science (En desarrollo):** Python, Scikit-Learn, FastAPI, Seaborn, Pandas

## 📂 Estructura del Proyecto

El repositorio sigue una estructura Monorepo para facilitar la orquestación y el desarrollo *end-to-end*:

```text
/
├── api-autenticacion/    # Servicio de identidad y generación JWT
├── api-inventario/       # Gestión de stock y base de datos propia
├── api-pedidos/          # Gestión de órdenes y base de datos propia
├── docker-compose.yml    # Orquestador de contenedores
└── .gitignore            # Filtro de archivos binarios y secretos