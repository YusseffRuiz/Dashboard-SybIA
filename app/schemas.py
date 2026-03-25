from pydantic import BaseModel
from typing import List, Dict, Any

class ChartData(BaseModel):
    label: str
    value: float

class AnalysisResponse(BaseModel): # Formato de salida
    query_text: str          # Lo que el usuario dijo
    sql_generated: str      # El SQL que la IA armó (para auditoría)
    main_chart_type: str    # "bar"
    data: List[ChartData]   # Los datos reales
    suggestions: List[str]  # ["pie", "line", "table"] para las miniaturas