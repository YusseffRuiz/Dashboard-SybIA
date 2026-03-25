import os
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Cargar variables
load_dotenv("data.env")

def test_connection():
    # 1. Definimos los componentes por separado
    server = os.getenv('DB_SERVER')  # 192.168.0.251
    port = os.getenv('DB_PORT')  # 5354
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASS')
    database = os.getenv('DB_NAME')
    driver = os.getenv('DB_DRIVER')

    # 2. Construcción manual del string (Formato Estándar ODBC)
    # Nota: A veces con Puerto + Instancia, el Server debe ser "IP,PORT"
    # y la instancia se ignora si el puerto es estático.
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"  # Probamos primero IP,PUERTO
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=no;"  # Importante para SQL 2017 local
        "TrustServerCertificate=yes;"
    )

    print(f"🔍 Intentando conectar a: {server}:{port}...")
    try:
        # Construcción del Connection String para SQL Server con Instancia y Puerto
        # Formato: server,port\instance
        connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"
        engine = create_engine(connection_url)

        df = pd.read_sql("SELECT TOP 1 * FROM AI.mv_ResumenPacientes", engine)
        print("Datos leídos correctamente.")
        print(df)

    except Exception as e:
        print(f"\n❌ Error de conexión: {e}")


if __name__ == "__main__":
    test_connection()