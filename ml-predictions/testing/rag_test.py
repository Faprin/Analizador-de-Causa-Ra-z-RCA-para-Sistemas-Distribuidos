from src.rag_engine import RAG

def anomaly_format(logs_anomalos):
    """Convierte los logs del Isolation Forest en una historia legible"""
    if not logs_anomalos:
        return "No hay datos."
    
    trace_id = logs_anomalos[0].get("traceId", "Desconocido")
    historia = f"TRACE_ID: {trace_id}\n\n"
    
    for i, log in enumerate(logs_anomalos, start=1):
        servicio = log.get("service", log.get("uri_servicio", "Desconocido"))
        duracion = log.get("duration_ms", "Desconocido")
        evento = log.get("event_type", "ERROR")
        texto = log.get("error_message", log.get("texto_completo", "Sin descripción"))
        
        historia += f"EVENTO {i} (DURACION: {duracion}ms):\n"
        historia += f"- SERVICIO: {servicio}\n"
        historia += f"- TIPO EVENTO: {evento}\n"
        historia += f"- MENSAJE: {texto}\n"
        historia += "-" * 40 + "\n"
    return historia

rag_model = RAG()

casos_de_prueba = [
    {
        "nombre": "ESCENARIO A: Fallo en Cascada Real (Saturación BD)",
        "logs": [
            {
                "traceId": "6a44c3c1-db-pool",
                "service": "api-inventario",
                "duration_ms": 29014,
                "event_type": "SERVER_ERROR",
                "error_message": "CannotCreateTransactionException - could not open JPA EntityManager for transaction"
            },
            {
                "traceId": "6a44c3c1-db-pool",
                "service": "api-pedidos",
                "duration_ms": 5273,
                "event_type": "UNHANDLED_ERROR",
                "error_message": "ResourceAccessException - Read timed out connecting to api-inventario"
            }
        ]
    },
    {
        "nombre": "ESCENARIO B: Error de Cliente (No es fallo de infraestructura)",
        "logs": [
            {
                "traceId": "8b55d4d2-bad-request",
                "service": "api-pedidos",
                "duration_ms": 45,
                "event_type": "VALIDATION_ERROR",
                "error_message": "MethodArgumentNotValidException - campo 'cantidad' faltante en el body"
            }
        ]
    },
    {
        "nombre": "ESCENARIO C: Trampa Anti-Alucinaciones (Servicio Inexistente)",
        "logs": [
            {
                "traceId": "9c66e5e3-fake-error",
                "service": "api-pagos",
                "duration_ms": 1500,
                "event_type": "CACHE_FATAL_ERROR",
                "error_message": "RedisCacheExplosionException - thermal runaway in cluster nodes"
            }
        ]
    }
]

print("🚀 Iniciando Auditoría del Experto Forense RAG...\n" + "="*50)

for caso in casos_de_prueba:
    print(f"\nEJECUTANDO: {caso['nombre']}")
    
    texto_formateado = anomaly_format(caso["logs"])
    
    print("ENVIANDO AL MODELO:\n" + texto_formateado)
    
    respuesta = rag_model.diagnose(texto_formateado)
    
    print("RESPUESTA DE LLAMA 3.1:")
    print("-" * 40)
    print(respuesta)
    print("=" * 50)