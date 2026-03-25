import re


class SQLValidator:
    def __init__(self):
        # Nuestra "Fuente de Verdad"
        self.schema = {
            "AI.mv_ResumenPacientes": [
                "total", "menores", "mayores", "sin_fecha_nacimiento",
                "masculino", "femenino", "titulares", "beneficiarios"
            ],
            "AI.mv_TotalPacientesXMes": [
                "Anio", "MesNum", "Mes", "Total"
            ],
        }

    def validate(self, sql_query):
        sql_upper = sql_query.upper()

        # 1. Seguridad Básica: Solo permitir SELECT
        if not sql_upper.strip().startswith("SELECT"):
            return False, "Operación no permitida. Solo se admiten consultas SELECT."

        # 2. Protección contra comandos destructivos (SQL Injection)
        forbidden_words = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]
        for word in forbidden_words:
            if word in sql_upper:
                return False, f"Palabra prohibida detectada: {word}"

        # 3. Validación de Columnas por Tabla
        for table, allowed_columns in self.schema.items():
            if table.upper() in sql_upper:
                # Extraemos todas las palabras del query para buscar columnas
                # Eliminamos caracteres especiales para evitar falsos negativos
                clean_query = re.sub(r"[(),;.]", " ", sql_upper)
                query_words = clean_query.split()

                # Revisamos columnas prohibidas para ESTA tabla específica
                # (Ejemplo: si estamos en TotalPacientesXMes, no puede haber 'menores')
                all_allowed_upper = [c.upper() for c in allowed_columns]

                # Lista de columnas que suelen causar conflicto
                conflictive_cols = ["MENORES", "MAYORES", "MASCULINO", "FEMENINO", "TITULARES", "ANIO"]

                for col in conflictive_cols:
                    if col in query_words and col not in all_allowed_upper:
                        return False, f"La columna '{col}' no existe en la tabla {table}."

        return True, "OK"