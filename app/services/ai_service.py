import os
import re

from llama_cpp import Llama

class SQLAgent:
    def __init__(self, llm_model_file, config=None):
        # El Prompt de Sistema con tus nuevas tablas de erpanIDWH
        self.context = f"""
        Eres un sistema clasificador de SQL para SQL Server.
        Tu esquema es 'AI' con solamente dos tablas de solo lectura que contienen los pacientes o visitantes separados por meses, años, mayoría o minoría de edad, género y si son titulares o beneficiarios.NUNCA debes usar columnas mixtas. 
        Responde únicamente con 'TRIGGER_GENERAL' para las siguientes situaciones:
        - Si el usuario pide algo en conjunto.
        - Si el usuario pide "resumen", "datos generales", "mi unidad", "sucursal" o cualquier cosa que requiera AMBAS tablas.
        - Si el usuario pide "Resumen de mi clínica" o "resumen de mi sucursal" o fases similares.
        Para todo lo que solamente necesite una sola tabla, haz lo siguiente con esta estructura de datos:
        1. AI.mv_ResumenPacientes
            - En la respuesta incluye la categoría por la que agrupas.
            - COLUMNAS:  [Id_cliente,Cliente, total, menores, mayores, masculino, femenino, titulares, beneficiarios]
            - CUÁNDO USAR: Si piden "edades", "género", "quiénes son", 'titulares' o 'beneficiarios', usa 'menores' y 'mayores' cualquier similar incluye en las columnas descritas.
            - REGLA: Esta tabla NO tiene columna 'Anio'. NO la uses para filtros de tiempo.
        2. AI.mv_TotalPacientesXMes
           - Tu SELECT SIEMPRE debe empezar con: SELECT Anio, Mes, Total.
           - Tu SELECT NUNCA debe ser 'Cliente' ni 'id_Cliente'.
           - COLUMNAS: [id_Cliente, Cliente, Anio, MesNum, Mes, Total]
           - CUÁNDO USAR: Si piden "año pasado", "meses", "tendencia", "cuántos vinieron en X fecha", "numero de pacientes en X año", , cualquier similar incluye en las columnas descritas.
           - REGLA: Esta tabla SOLO tiene la columna 'Total'. No sabe de géneros ni edades.
           - NUNCA respondas solo con la columna 'Cliente', tu SELECT SIEMPRE debe incluir las dimensiones temporales (Mes, Anio) junto con la métrica (Total).
                
        REGLAS ESTRICTAS:
        - Si el usuario pide "dime LOS pacientes", "quiénes son" o "lista de pacientes", DEBES interpretar esto como "dime CUÁNTOS pacientes". Las tablas ya tienen estos valores sin usar SUM.
        - NO uses columnas que no existan en la tabla seleccionada.
        - SIEMPRE filtra por id_cliente.
        - NUNCA utilices SELECT SUM(Total) ni GROUP BY en la tabla AI.mv_TotalPacientesXMes.
        - NUNCA realices un SELECT Cliente. Si el usuario pide múltiples años, asegúrate de traer siempre 'Anio' y 'Mes' en el SELECT y ordenar por ellos (ORDER BY Anio DESC, MesNum DESC).
        - Si piden 'Hombres', usa 'masculino'. Si piden 'Mujeres', usa 'femenino'.
        - Si piden 'visitas' o 'pacientes' en determinada cantidad de tiempo, usa los datos de AI.mv_TotalPacientesXMes, de los apartados 'Anio', 'Mes', 'Total' y la SQL query debe ser obtener el numero de pacientes separados por meses.
        - Para 'Año pasado', usa: WHERE Anio = YEAR(GETDATE()) - 1.
        - Si piden 'últimos 5 meses', usa: WHERE Anio = 2026 AND MesNum > (MONTH(GETDATE()) - 5).
        - El codigo SQL no debe contener campos inexistentes de los que tienes en el contexto, forza a que las peticiones quepan en dichos campos.
        - Devuelve SOLO el código SQL, sin markdown ni explicaciones encerrado entre [SQL] y [/SQL], no des mas explicaciones.
        - Si lo que pide NO EXISTE (ej. "ventas de medicinas"), responde: Sin existencia.
        """
        if config is None:
            gpu_layers = -1  # 20 a 30 funcionan en nuestra GPU NVIDIA RTX4090 8 GB, -1 settea a GPU
            config = {'max_new_tokens': 256, 'context_length': 2048, 'temperature': 0.45, "gpu_layers": gpu_layers,
                      "threads": os.cpu_count()}

        self.llm_model = Llama(model_path=llm_model_file,
                             n_ctx=config["context_length"],
                             # The max sequence length to use - note that longer sequence lengths require much more resources
                             n_threads=config["threads"],
                             # The number of CPU threads to use, tailor to your system and the resulting performance
                             n_gpu_layers=config['gpu_layers'],
                             temperature=config["temperature"],
                             n_batch=512,
                             use_mlock=False,
                             use_mmap=True,
                             f16_kv = True,
                             verbose=False
                             )

    def generate_query(self, user_text, client_id, test=False):
        # Aquí llamarías a un modelo (Llama-3 local o GPT)
        # Por ahora, simulamos la lógica:
        if test:
            if "género" in user_text.lower() or "sexo" in user_text.lower():
                return f"SELECT masculino, femenino FROM AI.mv_ResumenPacientes WHERE id_cliente = {client_id}"

            if "mes" in user_text.lower() or "histórico" in user_text.lower():
                return f"SELECT Anio, Mes, Total FROM AI.mv_TotalPacientesXMes WHERE id_cliente = {client_id} ORDER BY Anio, MesNum"

            return "SELECT * FROM AI.mv_ResumenPacientes"  # Default
        else:
            prompt = f"""[INST] <<SYS>>\n {self.context}\n <<SYS>>\n\n
                        el id_cliente o id_Cliente es {client_id}
                    Ejemplo 1: "Grafica de Pacientes por género"
                    Respuesta:Respuesta: SELECT masculino, femenino FROM AI.mv_ResumenPacientes WHERE id_cliente = {client_id};

                    Ejemplo 2: "Total de visitas durante el año pasado"
                    Respuesta: SELECT Mes, Total FROM AI.mv_TotalPacientesXMes WHERE id_Cliente = {client_id} AND Anio = YEAR(GETDATE()) - 1 ORDER BY MesNum;
                    
                    PREGUNTA: "{user_text} ".[/INST] 
                    """
            # print(prompt)
            response = self.llm_model(
                prompt,
                max_tokens=256,
                stop=["[/SQL]"],
                echo=False,
                stream=False,
            )
            # print("Response:", response)
            sql = response['choices'][0]['text'].strip()
            # print("Pre clean: ", sql)
            response = self.clean_sql_output(sql)
            # print("After clean: ", response)
            # Limpieza básica por seguridad
            if not response.upper().startswith("SELECT"):
                print(response)
                return "Error: La IA no generó un SELECT válido."

            return response if response.endswith(";") else f"{response};"

    def clean_sql_output(self, raw_output):
        # 1. Eliminar tags que estorben (limpieza literal)
        clean_text = raw_output.replace("[SQL]", "").replace("[/SQL]", "")
        clean_text = clean_text.replace("```sql", "").replace("```", "").strip()

        # 2. Buscar el bloque que empieza con SELECT y termina en el ÚLTIMO punto y coma
        # Usamos re.DOTALL para que el punto (.) incluya saltos de línea
        match = re.search(r"(SELECT.*?;)", clean_text, re.DOTALL | re.IGNORECASE)

        if match:
            sql = match.group(1).strip()
        else:
            # 3. Si no hay punto y coma, buscamos desde SELECT hasta el final del texto
            match_no_semi = re.search(r"(SELECT.*)", clean_text, re.DOTALL | re.IGNORECASE)
            sql = match_no_semi.group(1).strip() if match_no_semi else clean_text.strip()

        # 4. Eliminar posibles repeticiones de la palabra SELECT que la IA a veces duplica
        # (Como el error que te dio: "SELECT SELECT;")
        if sql.upper().startswith("SELECT SELECT"):
            sql = sql[7:]

        sql = sql.replace(r"\_", "_")

        # 2. Elimina los bloques de código (ticks) por si Mistral decide agregarlos
        sql = sql.replace("```sql", "").replace("```", "").strip()

        return sql

    @staticmethod
    def get_correct_table(user_text):
        text = user_text.lower()
        # Palabras clave que OBLIGAN a usar la tabla de Resumen
        if any(word in text for word in ["menor", "mayor", "genero", "sexo", "titular", "hombres", "mujeres"]):
            return "AI.mv_ResumenPacientes"
        return "AI.mv_TotalPacientesXMes"

    @staticmethod
    def get_static_dashboard_queries(id_cliente):
        # Query 1: Demografía Detallada
        # Trae: Totales, Género, Edades y Parentesco en una sola fila.
        query_demografia = f"""
            SELECT 
                total, masculino, femenino, 
                menores, mayores, sin_fecha_nacimiento,
                titulares, beneficiarios
            FROM AI.mv_ResumenPacientes
            WHERE id_cliente = {id_cliente};
            """

        # Query 2 histórico:
        # Trae: El comportamiento de los últimos 12 meses (o año actual).
        # Nota: Filtramos por el año 2025/2026 según datos actuales.
        query_historico = f"""
            SELECT 
                Anio, MesNum, Mes, Total
            FROM AI.mv_TotalPacientesXMes
            WHERE id_Cliente = {id_cliente}
              AND (Anio = 2025 OR Anio = 2026)
            ORDER BY Anio DESC, MesNum DESC;
            """

        return {
            "demografia": query_demografia,
            "historico": query_historico
        }