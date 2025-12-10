from fastapi import APIRouter
import pandas as pd
import numpy as np
import os

router = APIRouter()
RUTA = os.getenv("EXCEL_PATH", "Dados_abertos_Consumo_Mensal.xlsx")

# Cargar hojas
df_ind = pd.read_excel(RUTA, sheet_name="SETOR INDUSTRIAL POR RG")
df_sam = pd.read_excel(RUTA, sheet_name="CONSUMO E NUMCONS SAM")

df_ind["DataExcel"] = pd.to_datetime(df_ind["DataExcel"])
df_sam["DataExcel"] = pd.to_datetime(df_sam["DataExcel"])

# ============================
# FUNCIONES
# ============================

def estadisticas(s):
    return {
        "media": float(s.mean()),
        "mediana": float(s.median()),
        "desviacion": float(s.std()),
        "minimo": float(s.min()),
        "maximo": float(s.max())
    }

# ============================
# ENDPOINTS MODERNOS
# ============================

@router.get("/actual/estadisticas-industrial")
def estadisticas_industrial():
    return estadisticas(df_ind["Consumo"])

@router.get("/actual/serie-industrial")
def serie_industrial():
    g = df_ind.groupby("DataExcel")["Consumo"].sum().reset_index()
    return g.to_dict(orient="records")

@router.get("/actual/picos-industrial")
def picos_industrial():
    m = df_ind["Consumo"].mean()
    d = df_ind["Consumo"].std()
    p = df_ind[df_ind["Consumo"] > m + 2*d]
    return p.to_dict(orient="records")

@router.get("/actual/estadisticas-sam")
def estadisticas_sam():
    return estadisticas(df_sam["Consumo"])
