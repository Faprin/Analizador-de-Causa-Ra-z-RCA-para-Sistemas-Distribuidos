# ==========================================
# ETAPA 1: Compilación (Build)
# ==========================================
FROM maven:3.9.6-eclipse-temurin-21 AS builder

# Definimos la carpeta de trabajo dentro de este contenedor temporal
WORKDIR /build

# Copiamos primero el archivo pom.xml para descargar las dependencias.
# Esto se hace primero para aprovechar la caché de capas de Docker y acelerar futuros builds.
COPY pom.xml .

# Descargamos las dependencias necesarias sin compilar el código todavía
RUN mvn dependency:go-offline -B

# Ahora copiamos la carpeta con todo nuestro código fuente (src)
COPY src ./src

# Compilamos el proyecto y empaquetamos el archivo .jar 
# (Omitimos los tests temporales para agilizar la construcción en el contenedor)
RUN mvn clean package -DskipTests

# ==========================================
# ETAPA 2: Entorno de Ejecución (Runtime)
# ==========================================
# Usamos una imagen muy reducida basada en Alpine Linux que solo contiene el JRE (entorno de ejecución)
FROM eclipse-temurin:21-jre-alpine

# Definimos el directorio donde residirá nuestra aplicación final
WORKDIR /app

# Copiamos únicamente el archivo .jar que se generó en la etapa anterior (builder)
# De esta forma, nos dejamos atrás todo el código fuente y las herramientas de Maven, reduciendo el tamaño
COPY --from=builder /build/target/*.jar app.jar

# Informamos a Docker del puerto en el que nuestra aplicación escucha peticiones (Spring Boot usa el 8080 por defecto)
EXPOSE 8080

# Definimos el comando definitivo que se ejecutará de forma automática al encender el contenedor
ENTRYPOINT ["java", "-jar", "app.jar"]