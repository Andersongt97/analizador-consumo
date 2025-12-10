from fastapi import APIRouter
import pandas as pd
import numpy as np
import os

router = APIRouter()
RUTA = os.getenv("EXCEL_PATH", "Dados_abertos_Consumo_Mensal.xlsx")

df_70 = pd.read_excel(RUTA, sheet_name="CONSUMO_BEN_RG_1970-1989")
df_90 = pd.read_excel(RUTA, sheet_name="CONSUMO_ELETROBRAS_1990-2003")

def tendencia(df):
    s = df["Consumo"]
    x = np.arange(len(s))
    y = s.values
    m, _ = np.polyfit(x, y, 1)
    return {"pendiente": float(m)}

@router.get("/historico/tendencia-1970-1989")
def tendencia_70():
    return tendencia(df_70)

@router.get("/historico/tendencia-1990-2003")
def tendencia_90():
    return tendencia(df_90)
