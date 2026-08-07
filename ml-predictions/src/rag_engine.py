from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import os

FAISS_PATH = os.path.join(os.path.dirname(__file__), "vectorstore/faiss_index")
template = """
    Eres un Ingeniero SRE (Site Reliability Engineer) y Experto Forense de Nivel 3. 
    Tu especialidad es diagnosticar fallos en cascada en una arquitectura de microservicios Spring Boot (api-pedidos, api-inventario, api-autenticacion).

    Has recibido una alerta de nuestro modelo de Machine Learning (Isolation Forest) indicando que el siguiente bloque de logs es una ANOMALÍA CRÍTICA.

    REGLAS ESTRICTAS:
    1. NO inventes información. Utiliza ÚNICAMENTE la documentación técnica y los runbooks proporcionados en el apartado <contexto>.
    2. Si el <contexto> no contiene la respuesta, di explícitamente: "No hay información suficiente en los manuales para determinar la causa raíz."
    3. Debes diferenciar el "paciente cero" (causa raíz) de las víctimas (errores en cascada).

    <contexto>
    {context}
    </contexto>

    FORMATO DE RESPUESTA OBLIGATORIO:
    Responde siempre usando esta estructura en Markdown:

    🚨 **Análisis de Causa Raíz (RCA)**
    * **Microservicio Origen:** [Nombre del servicio que falló primero]
    * **Excepción Principal:** [Tipo de error, ej. NullPointerException, Timeout]
    * **Diagnóstico:** [Explicación técnica de 4 o 5 líneas de por qué ocurrió según el contexto]

    🛠️ **Plan de Mitigación (Runbook)**
    - Genera tantos pasos como sean necesarios para mitigar el problema
"""

class RAG:
    def __init__(self):

        # inicializacion del modelo 
        self.llm = ChatOllama(
            model = "llama3.2:3b",
            temperature=0.0
        )

        self.embeddings = OllamaEmbeddings(
            model = "nomic-embed-text"
        )

        self.vectorstore = FAISS.load_local(
            FAISS_PATH,
            self.embeddings,
            allow_dangerous_deserialization=True            
        )

        self.retriever = self.vectorstore.as_retriever()

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", template),
            # MessagesPlaceholder(variable='history'),
            ("human", "Analiza este log anomalo y dime qué ha pasado: \n\n{input}")
        ])

        def faiss_search(entry_dic):
            docs = self.retriever.invoke(entry_dic["input"])
            return "\n\n".join(doc.page_content for doc in docs)

        self.rag_chain = (
            RunnablePassthrough.assign(context=faiss_search)
            | self.prompt
            | self.llm
            | StrOutputParser
        )

        print("[RAG SYSTEM] Motor RAG cargado")

    def diagnose(self, formatted_text: str) -> str:
        try: 
            response = self.rag_chain.invoke({"input": formatted_text})
            return response
        
        except Exception as e:
            return f"Error en RAG: {str(e)}"

rag_engine = RAG()