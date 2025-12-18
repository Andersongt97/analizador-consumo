from fastapi import APIRouter
import pandas as pd
import numpy as np
import os

router = APIRouter()

# Ruta del Excel configurable por variable de entorno
RUTA = os.getenv("EXCEL_PATH", "Dados_abertos_Consumo_Mensal.xlsx")

# Carga hojas históricas
df_70 = pd.read_excel(RUTA, sheet_name="CONSUMO_BEN_RG_1970-1989")
df_90 = pd.read_excel(RUTA, sheet_name="CONSUMO_ELETROBRAS_1990-2003")

def tendencia(df):
    """
    Calcula una tendencia lineal simple sobre la columna 'Consumo':
    - x = índice 0..n-1
    - y = consumo
    Devuelve la pendiente (m) del ajuste lineal y = m*x + b.
    """
    s = df["Consumo"]
    x = np.arange(len(s))
    y = s.values

    # polyfit grado 1 => recta. Retorna (m, b)
    m, _ = np.polyfit(x, y, 1)
    return {"pendiente": float(m)}

@router.get("/historico/tendencia-1970-1989")
def tendencia_70():
    """Pendiente/tendencia para el periodo 1970–1989."""
    return tendencia(df_70)

@router.get("/historico/tendencia-1990-2003")
def tendencia_90():
    """Pendiente/tendencia para el periodo 1990–2003."""
    return tendencia(df_90)
