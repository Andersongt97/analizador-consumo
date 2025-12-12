import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from io import BytesIO
import qrcode

# ============================
# CONFIGURACIÓN BÁSICA
# ============================
API_URL = "http://127.0.0.1:8000"  # FastAPI
DASHBOARD_URL = "http://localhost:8501"  # URL que irá en el QR (ajústala si usas otra IP)

st.set_page_config(
    page_title="Dashboard Energético Brasil",
    layout="wide"
)

st.title(" Dashboard de Consumo Energético por Región - Brasil")
st.caption("Backend: FastAPI • Frontend: Streamlit • Datos: Excel oficial por regiones")


# ============================
# FUNCIONES AUXILIARES
# ============================
@st.cache_data
def get_regiones():
    resp = requests.get(f"{API_URL}/catalogos/regioes")
    resp.raise_for_status()
    return resp.json()["regioes"]

@st.cache_data
def get_datos_industrial():
    resp = requests.get(f"{API_URL}/consumo/datos-industrial")
    resp.raise_for_status()
    datos = resp.json()
    df = pd.DataFrame(datos)
    # Normalizar fecha
    if "DataExcel" in df.columns:
        df["DataExcel"] = pd.to_datetime(df["DataExcel"])
        df["Ano"] = df["DataExcel"].dt.year
        df["Mes"] = df["DataExcel"].dt.month
        df["AnoMes"] = df["DataExcel"].dt.to_period("M").astype(str)
    return df

@st.cache_data
def generar_qr(url: str) -> BytesIO:
    """Genera un código QR en memoria para una URL dada."""
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def generar_informe_txt(region_sel, sector_sel, df_region, stats):
    """Crea el texto del informe en base a los filtros y estadísticas."""
    lineas = []
    lineas.append("INFORME DE CONSUMO ENERGÉTICO POR REGIÓN - BRASIL")
    lineas.append("------------------------------------------------")
    lineas.append(f"Región seleccionada: {region_sel}")
    lineas.append(f"Sector industrial: {sector_sel if sector_sel != '(Todos)' else 'Todos los sectores'}")
    lineas.append(f"Total de registros considerados: {len(df_region)}")
    lineas.append("")
    lineas.append("ESTADÍSTICAS BÁSICAS DEL CONSUMO (MWh)")
    lineas.append(f"- Media: {stats['media']:.2f}")
    lineas.append(f"- Mediana: {stats['mediana']:.2f}")
    lineas.append(f"- Desviación estándar: {stats['desviacion']:.2f}")
    lineas.append(f"- Mínimo: {stats['minimo']:.2f}")
    lineas.append(f"- Máximo: {stats['maximo']:.2f}")
    lineas.append("")
    lineas.append("OBSERVACIONES GENERALES:")
    lineas.append("- El informe resume el comportamiento del consumo energético")
    lineas.append("  para la región y el sector seleccionados, con base en los datos")
    lineas.append("  oficiales cargados desde el archivo Excel.")
    lineas.append("- Estos resultados pueden utilizarse como insumo para propuestas")
    lineas.append("  de optimización, monitoreo y análisis de tendencias en el sector energético.")
    lineas.append("")
    lineas.append("Generado automáticamente por el sistema FastAPI + Streamlit.")
    
    texto = "\n".join(lineas)
    return texto.encode("utf-8")


# ============================
# CARGA DE DATOS
# ============================
with st.spinner("Cargando datos desde la API..."):
    regiones = get_regiones()
    df = get_datos_industrial()

# ============================
# SIDEBAR DE FILTROS
# ============================
st.sidebar.header("Filtros")

region_sel = st.sidebar.selectbox("Seleccione una región de Brasil:", regiones)
sector_sel = st.sidebar.selectbox(
    "Filtrar por sector industrial (opcional):",
    ["(Todos)"] + sorted(df["SetorIndustrial"].dropna().unique().tolist())
)

# Filtro aplicado
df_region = df[df["Regiao"] == region_sel].copy()
if sector_sel != "(Todos)":
    df_region = df_region[df_region["SetorIndustrial"] == sector_sel]

st.sidebar.markdown(f"**Registros filtrados:** {len(df_region)}")


# ============================
# SECCIÓN 1: TABLA Y MÉTRICAS
# ============================
st.subheader(
    f"📋 Datos filtrados - Región: {region_sel}"
    + ("" if sector_sel == "(Todos)" else f" | Sector: {sector_sel}")
)

with st.expander("Ver tabla de datos filtrados"):
    st.dataframe(df_region)

stats = None
if not df_region.empty:
    media = df_region["Consumo"].mean()
    mediana = df_region["Consumo"].median()
    desv = df_region["Consumo"].std()
    minimo = df_region["Consumo"].min()
    maximo = df_region["Consumo"].max()

    stats = {
        "media": media,
        "mediana": mediana,
        "desviacion": desv,
        "minimo": minimo,
        "maximo": maximo
    }

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Media", f"{media:,.2f} MWh")
    c2.metric("Mediana", f"{mediana:,.2f} MWh")
    c3.metric("Desviación", f"{desv:,.2f}")
    c4.metric("Mínimo", f"{minimo:,.2f} MWh")
    c5.metric("Máximo", f"{maximo:,.2f} MWh")
else:
    st.warning("No hay datos para los filtros seleccionados.")

st.markdown("---")


# ============================
# SECCIÓN 2: GRÁFICAS PRINCIPALES
# ============================
st.subheader("📊 Visualizaciones del consumo")

if df_region.empty:
    st.info("Ajusta los filtros para ver gráficos.")
else:
    col1, col2 = st.columns(2)

    # 1) HISTOGRAMA de consumo
    with col1:
        st.markdown("#### Histograma de Consumo")
        fig_hist = px.histogram(
            df_region,
            x="Consumo",
            nbins=30,
            title="Distribución del consumo (MWh)"
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # 2) GRÁFICA DE TORTA (PIE) por sector
    with col2:
        st.markdown("#### Participación por Sector Industrial")
        df_pie = df_region.groupby("SetorIndustrial", as_index=False)["Consumo"].sum()
        fig_pie = px.pie(
            df_pie,
            values="Consumo",
            names="SetorIndustrial",
            title="Participación del consumo por sector industrial"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    col3, col4 = st.columns(2)

    # 3) BARRAS: Consumo por año
    with col3:
        st.markdown("#### Consumo total por año")
        df_bar = df_region.groupby("Ano", as_index=False)["Consumo"].sum()
        fig_bar = px.bar(
            df_bar,
            x="Ano",
            y="Consumo",
            title="Consumo anual (MWh)",
            text_auto=".2s"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # 4) DISPERSIÓN: Fecha vs Consumo (color por sector)
    with col4:
        st.markdown("#### Dispersión temporal del consumo")
        fig_scatter = px.scatter(
            df_region,
            x="DataExcel",
            y="Consumo",
            color="SetorIndustrial",
            title="Consumo por fecha y sector",
            hover_data=["Regiao", "SetorIndustrial"]
        )
        st.plotly_chart(fig_scatter, use_container_width=True)


# ============================
# SECCIÓN 3: MAPA DE CALOR POR REGIÓN
# ============================
st.subheader(" Mapa de calor por región de Brasil (Consumo agregado)")

df_heat = df.groupby(["Regiao", "AnoMes"], as_index=False)["Consumo"].sum()

if df_heat.empty:
    st.warning("No hay datos para construir el mapa de calor.")
else:
    tabla_heat = df_heat.pivot(index="Regiao", columns="AnoMes", values="Consumo").fillna(0)

    fig_heat = px.imshow(
        tabla_heat,
        labels=dict(x="Año-Mes", y="Región", color="Consumo (MWh)"),
        aspect="auto",
        title="Mapa de calor de consumo por región y periodo (Brasil)"
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    with st.expander("Ver tabla usada para el mapa de calor"):
        st.dataframe(tabla_heat)


st.markdown("---")

# ============================
# SECCIÓN 4: INFORME DESCARGABLE
# ============================
st.subheader(" Descarga de informe y datos filtrados")

col_inf1, col_inf2 = st.columns(2)

if stats is not None and not df_region.empty:
    # Informe en TXT
    informe_bytes = generar_informe_txt(region_sel, sector_sel, df_region, stats)
    col_inf1.download_button(
        label="📥 Descargar informe en TXT",
        data=informe_bytes,
        file_name=f"informe_consumo_{region_sel.replace(' ', '_')}.txt",
        mime="text/plain"
    )

    # Datos filtrados en CSV
    csv_bytes = df_region.to_csv(index=False).encode("utf-8")
    col_inf2.download_button(
        label="📥 Descargar datos filtrados (CSV)",
        data=csv_bytes,
        file_name=f"datos_filtrados_{region_sel.replace(' ', '_')}.csv",
        mime="text/csv"
    )
else:
    st.info("No hay datos ni estadísticas para generar informe con los filtros actuales.")

st.markdown("---")

# ============================
# SECCIÓN 5: CÓDIGO QR DEL DASHBOARD
# ============================
st.subheader("🔳 Consultar el dashboard mediante código QR")

st.markdown(
    "Escanea este código QR desde tu celular para abrir el dashboard "
    "en la misma red local (ajusta la URL en `DASHBOARD_URL` si lo expones en otra IP)."
)

qr_buffer = generar_qr(DASHBOARD_URL)
st.image(qr_buffer, caption=DASHBOARD_URL, width=200)

st.download_button(
    label=" Descargar imagen del QR",
    data=qr_buffer,
    file_name="dashboard_qr.png",
    mime="image/png"
)

st.success("Dashboard generado correctamente usando datos de la API FastAPI.")
