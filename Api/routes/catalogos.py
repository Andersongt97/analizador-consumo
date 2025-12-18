from fastapi import APIRouter
import pandas as pd
import os

# Router independiente (se monta en main.py)
router = APIRouter()

# Ruta del Excel configurable por variable de entorno
RUTA_EXCEL = os.getenv("EXCEL_PATH", "Dados_abertos_Consumo_Mensal.xlsx")

# Carga una sola hoja (industrial por región) para construir catálogos
df = pd.read_excel(RUTA_EXCEL, sheet_name="SETOR INDUSTRIAL POR RG")
df["DataExcel"] = pd.to_datetime(df["DataExcel"])

# =========================
# CATÁLOGOS SOLO POR REGIÓN
# =========================

@router.get("/regioes")
def catalogo_regioes():
    """
    Devuelve la lista de regiones únicas disponibles.
    Importante: son REGIONES (Regiao), no estados (UF).
    """
    regioes = sorted(df["Regiao"].dropna().unique().tolist())
    return {"regioes": regioes}


@router.get("/setores-industriais")
def catalogo_setores():
    """
    Devuelve la lista de sectores industriales únicos disponibles.
    """
    setores = sorted(df["SetorIndustrial"].dropna().unique().tolist())
    return {"setores": setores}
