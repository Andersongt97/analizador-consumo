from fastapi import APIRouter
import pandas as pd
import os

router = APIRouter()

RUTA_EXCEL = os.getenv("EXCEL_PATH", "Dados_abertos_Consumo_Mensal.xlsx")

# SOLO hoja por REGIÓN
df = pd.read_excel(RUTA_EXCEL, sheet_name="SETOR INDUSTRIAL POR RG")
df["DataExcel"] = pd.to_datetime(df["DataExcel"])

# =========================
# CATÁLOGOS SOLO POR REGIÓN
# =========================

@router.get("/regioes")
def catalogo_regioes():
    """
    Devuelve solo las REGIONES (no estados).
    """
    regioes = sorted(df["Regiao"].dropna().unique().tolist())
    return {"regioes": regioes}


@router.get("/setores-industriais")
def catalogo_setores():
    """
    Devuelve solo los SECTORES INDUSTRIALES por REGIÓN.
    """
    setores = sorted(df["SetorIndustrial"].dropna().unique().tolist())
    return {"setores": setores}
