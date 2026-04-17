import time
import json
import os
from datetime import datetime
from functools import wraps

def audit_logger(log_name="audit.log"):
    def decorador(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_msg = None
            extracted_transcript = "N/A"

            try:
                # Ejecuta la función original
                result = await func(*args, **kwargs)

                if result and isinstance(result, dict):
                    extracted_transcript = result.get("transcript", "N/A")

                return result

            except Exception as e:
                success = False
                error_msg = str(e)
                raise e  # Re-lanzamos para que FastAPI maneje el 500
            finally:
                end_time = time.time()
                latency = (end_time - start_time) * 1000  # Convertir a milisegundos

                # Estructura del Log Nivel Doctorado
                log_entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "function": func.__name__,
                    "latency_ms": round(latency, 2),
                    "success": success,
                    "error": error_msg,
                    # Extraemos el texto del usuario si está en los argumentos
                    "user_input": extracted_transcript
                }

                # Guardado persistente
                log_path = f"logs/{log_name}.jsonl"
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        return wrapper
    return decorador