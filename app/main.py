import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import create_engine
import pandas as pd
import shutil
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from app.services.stt_service import AsrEngine
from app.services.ai_service import SQLAgent
from app.utils.logger import audit_logger
from app.utils.validator import SQLValidator

BASE_DIR = Path(__file__).resolve().parent.parent   # sube un nivel
ENV_PATH = BASE_DIR / "data.env"
load_dotenv(ENV_PATH)
LLM_MODEL_FILE = os.getenv("LLM_MODEL_FILE")
app = FastAPI(title="AI Medical Analytics API", version="1.0.0")
stt = AsrEngine(model_size="medium")
sql_agent = SQLAgent(llm_model_file=LLM_MODEL_FILE)
validator = SQLValidator()


# --- 2. CONFIGURACIÓN DE CORS (Vital para el Frontend) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite conexiones desde cualquier index.html local
    allow_credentials=True,
    allow_methods=["*"], # Permite GET, POST, OPTIONS, etc.
    allow_headers=["*"],
)

server = os.getenv('DB_SERVER')  # 192.168.0.251
port = os.getenv('DB_PORT')  # 5354
user = os.getenv('DB_USER')
password = os.getenv('DB_PASS')
database = os.getenv('DB_NAME')
driver = os.getenv('DB_DRIVER')

conn_str = (
        f"DRIVER={driver};"
        f"SERVER={server},{port};"  
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=no;" 
        "TrustServerCertificate=yes;"
    )
print(conn_str)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={conn_str}")

@app.get("/health")
async def health():
    return {"message": "AI Medical System Active", "responsible": "Transformación Digital"}


@app.get("/health/db")
async def verify_db_connection():
    """
    Endpoint de diagnóstico para verificar la conexión a MSSQL
    """
    try:
        # Extraemos la conexión cruda (raw connection) evadiendo SQLAlchemy Core
        raw_conn = engine.raw_connection()

        try:
            cursor = raw_conn.cursor()
            cursor.execute("SELECT @@VERSION")
            result = cursor.fetchone()

            return {
                "status": "success",
                "network_path": f"{server}:{port}",
                "message": "Conexión bidireccional establecida por túnel NAT.",
                "sql_version": result[0]
            }
        finally:
            # Es vital cerrar la conexión cruda manualmente para no saturar el pool
            cursor.close()
            raw_conn.close()

    except Exception as e:
        print(f"[ERROR CRÍTICO DB] Fallo en la conexión hacia {server}:{port}. Detalle: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Servicio no disponible. Verifica el firewall o las credenciales. Error: {str(e)}"
        )

@app.get("/get-sucursales")
@audit_logger(log_name="config_logs") # Reutilizamos su logger dinámico
async def get_sucursales():
    # Query para traer los IDs y Nombres únicos
    query = "SELECT DISTINCT id_Cliente, Cliente FROM AI.mv_TotalPacientesXMes ORDER BY Cliente ASC"
    try:
        df = pd.read_sql(query, engine)
        # print(df.to_dict(orient="records"))
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice-request")
async def process_voice(file: UploadFile = File(...)):
    # 1. Guardar el audio temporalmente
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Transcribir
    text_query = stt.transcribe(temp_path)

    # 3. Limpiar temporal
    os.remove(temp_path)

    return {"status": "success", "transcript": text_query}


@app.post("/analyze-voice")
@audit_logger(log_name="voice_queries_logger")
async def analyze_voice(file: UploadFile = File(...), id_cliente: int = 1):
    """
    Endpoint principal: Recibe audio, transcribe y consulta SQL.
    """
    temp_file = f"temp_{file.filename}"

    try:
        # A. Guardar audio temporalmente
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # B. Transcripción (Oído)
        transcript, confidence = stt.transcribe(temp_file)
        if transcript is None:
            raise HTTPException(status_code=400, detail="No transcription found.")
        print(f"🎙️ Usuario dijo: {transcript}")

        # C. Lógica de Enrutamiento (Cerebro Inicial)
        # Aquí es donde determinamos qué tabla de 'AI.mv_' usar
        query = sql_agent.generate_query(user_text=transcript, client_id=id_cliente, test=False)
        # 1. ¿Es una consulta general o fallida?
        if "TRIGGER_GENERAL" in query.upper():
            queries = sql_agent.get_static_dashboard_queries(id_cliente)

            # Ejecución en paralelo (lógica simplificada)
            df_demo = pd.read_sql(queries["demografia"], engine)
            df_hist = pd.read_sql(queries["historico"], engine)

            return {
                "transcript": transcript,
                "intent": "dashboard_general",
                "visualization": {
                    "pie_charts": ["Genero", "Edad", "Parentesco"],
                    "line_chart": "Tendencia Mensual"
                },
                "data": {
                    "resumen": df_demo.to_dict(orient="records"),
                    "timeline": df_hist.to_dict(orient="records")
                }
            }
        print(query)
        is_valid, message = validator.validate(query)

        if not is_valid:
            queries = sql_agent.get_static_dashboard_queries(id_cliente)

            # Ejecución en paralelo (lógica simplificada)
            df_demo = pd.read_sql(queries["demografia"], engine)
            df_hist = pd.read_sql(queries["historico"], engine)

            return {
                "transcript": transcript,
                "intent": "dashboard_general",
                "visualization": {
                    "pie_charts": ["Genero", "Edad", "Parentesco"],
                    "line_chart": "Tendencia Mensual"
                },
                "data": {
                    "resumen": df_demo.to_dict(orient="records"),
                    "timeline": df_hist.to_dict(orient="records")
                }
            }
            # raise HTTPException(status_code=400, detail=message)
        # D. Ejecución en SQL Server (Data)
        try:
            df = pd.read_sql(query, engine)
        except Exception as e:
            print(f"❌ SQL Server Error: {e}")
            df = pd.DataFrame()

        # E. Respuesta para el Frontend
        print(df.to_dict(orient="records"))
        return {
            "transcript": transcript,
            "sql_executed": query,
            "data": df.to_dict(orient="records"),  # Convertimos DataFrame a JSON
            "chart_type": "line" if "mes" in query else "bar"
        }

    except HTTPException as http_exception:
        raise http_exception

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Limpieza de archivos temporales
        if os.path.exists(temp_file):
            os.remove(temp_file)


WEBDEV_DIR = BASE_DIR / "app" / "WebDev"

if WEBDEV_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEBDEV_DIR), html=True), name="frontend")
else:
    print(f"⚠️ CRÍTICO: No se encontró la carpeta frontend en {WEBDEV_DIR}")