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
    Tu única misión es diagnosticar fallos utilizando EXCLUSIVAMENTE la información técnica proporcionada en el apartado <contexto>.

    <contexto>
    {context}
    </contexto>

    LOG ANÓMALO A ANALIZAR:
    {input}

    REGLAS DE RESPUESTA ESTRICTAS (LEER ATENTAMENTE):
    1. Nuestra arquitectura SOLO tiene 3 servicios: api-pedidos, api-inventario, api-autenticacion.
    2. Compara el log con el <contexto>. Si el log menciona un microservicio, base de datos o tecnología (ej. Redis, api-pagos) que NO está detallado en el <contexto>, TIENES PROHIBIDO inventar un diagnóstico.
    3. Si ocurre lo descrito en la regla 2, tu respuesta debe ser EXACTAMENTE Y ÚNICAMENTE esta frase: "No hay información suficiente en los manuales para determinar la causa raíz."

    Si el error SÍ está documentado en el contexto, usa estrictamente este formato:

    🚨 **Análisis de Causa Raíz (RCA)**
    * **Microservicio Origen:** [Nombre]
    * **Excepción Principal:** [Excepción]
    * **Diagnóstico:** [Explicación técnica basada SOLO en el contexto]

    🛠️ **Plan de Mitigación (Runbook)**
    1. [Paso 1 del contexto]
    2. [Paso 2 del contexto]
"""

class RAG:
    def __init__(self, docker: bool = False):

        base_url = "http://host.docker.internal:11434" if docker else "http://localhost:11434"

        # inicializacion del modelo 
        self.llm = ChatOllama(
            model = "llama3.2:3b",
            temperature=0.0,
            base_url= base_url
        )

        self.embeddings = OllamaEmbeddings(
            model = "nomic-embed-text",
            base_url=base_url
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
            | StrOutputParser()
        )

        print("[RAG SYSTEM] Motor RAG cargado")

    def diagnose(self, formatted_text: str) -> str:
        try: 
            response = self.rag_chain.invoke({"input": formatted_text})
            return response
        
        except Exception as e:
            return f"Error en RAG: {str(e)}"

rag_engine = RAG()