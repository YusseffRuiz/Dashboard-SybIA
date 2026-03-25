from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "sa")
DB_PASS = os.getenv("DB_PASS", "TuPasswordSeguro")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "NombreDeTuBD")

# El driver que ya confirmamos que tienes
DRIVER = "ODBC Driver 17 for SQL Server"

connection_string = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={DB_HOST},{DB_PORT};"
    f"DATABASE={DB_NAME};" # El nombre de la base de datos
    f"UID={DB_USER};"
    f"PWD={DB_PASS};"
)

engine = create_engine(connection_string, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_data(sql_query):
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    cursor.execute(sql_query)

    # Convertimos a una lista de diccionarios (lo que el Frontend ama)
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()
    return results