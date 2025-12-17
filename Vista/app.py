import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from io import BytesIO
import qrcode

# (Opcional) solo si usarás geopandas para validar/leer geojson
import json

# ============================
# CONFIGURACIÓN
# ============================
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501")

# GeoJSON del mapa (debes tenerlo local)
GEOJSON_PATH = os.getenv("GEOJSON_PATH", "data/br_states.geojson")

# Clave dentro del geojson para enlazar con tu columna de ubicación
# Ejemplo típico: "properties.sigla" o "properties.UF" o "properties.name"
GEOJSON_KEY = os.getenv("GEOJSON_KEY", "properties.sigla")

st.set_page_config(page_title="Dashboard Energético Brasil", layout="wide")

st.title("📊 Dashboard de Consumo Energético por Región - Brasil")
st.caption("Backend: FastAPI • Frontend: Streamlit • Datos: Excel oficial por regiones")

# ============================
# FUNCIONES AUXILIARES
# ============================
@st.cache_data
def get_regiones():
    resp = requests.get(f"{API_URL}/catalogos/regioes", timeout=30)
    resp.raise_for_status()
    return resp.json()["regioes"]

@st.cache_data
def get_datos_industrial():
    resp = requests.get(f"{API_URL}/consumo/datos-industrial", timeout=60)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())

    if "DataExcel" in df.columns:
        df["DataExcel"] = pd.to_datetime(df["DataExcel"], errors="coerce")
        df = df.dropna(subset=["DataExcel"])
        df["Ano"] = df["DataExcel"].dt.year
        df["Mes"] = df["DataExcel"].dt.month
        df["AnoMes"] = df["DataExcel"].dt.to_period("M").astype(str)

    return df

def generar_qr(url: str) -> BytesIO:
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

@st.cache_data
def load_geojson(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================
# CARGA DE DATOS
# ============================
with st.spinner("Cargando datos desde la API..."):
    try:
        regiones = get_regiones()
        df = get_datos_industrial()
    except Exception as e:
        st.error("No se pudo conectar a la API.")
        st.exception(e)
        st.stop()

# ============================
# SIDEBAR
# ============================
st.sidebar.header("Filtros")

region_sel = st.sidebar.selectbox("Seleccione una región:", regiones)

sector_sel = st.sidebar.selectbox(
    "Filtrar por sector:",
    ["(Todos)"] + sorted(df["SetorIndustrial"].dropna().unique())
)

df_region = df[df["Regiao"] == region_sel].copy()
if sector_sel != "(Todos)":
    df_region = df_region[df_region["SetorIndustrial"] == sector_sel]

st.sidebar.markdown(f"**Registros filtrados:** {len(df_region)}")

# ============================
# SECCIÓN 1: TABLA + MÉTRICAS
# ============================
st.subheader(f"📋 Datos filtrados - {region_sel}")

with st.expander("Ver tabla de datos filtrados"):
    st.dataframe(df_region, use_container_width=True)

if not df_region.empty:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Media", f"{df_region['Consumo'].mean():,.2f} MWh")
    c2.metric("Mediana", f"{df_region['Consumo'].median():,.2f} MWh")
    c3.metric("Desviación", f"{df_region['Consumo'].std():,.2f}")
    c4.metric("Mínimo", f"{df_region['Consumo'].min():,.2f} MWh")
    c5.metric("Máximo", f"{df_region['Consumo'].max():,.2f} MWh")
else:
    st.warning("No hay datos para los filtros seleccionados.")

st.markdown("---")

# ============================
# SECCIÓN 2: GRÁFICAS
# ============================
st.subheader("📊 Visualizaciones del consumo")

if df_region.empty:
    st.info("Ajusta los filtros para ver gráficos.")
else:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Histograma de consumo")
        fig_hist = px.histogram(df_region, x="Consumo", nbins=30)
        st.plotly_chart(fig_hist, use_container_width=True)

    with col2:
        st.markdown("#### Participación por Sector Industrial")

        df_pie = (
            df_region.groupby("SetorIndustrial", as_index=False)["Consumo"]
            .sum()
            .sort_values("Consumo", ascending=False)
        )

        if df_pie.empty or df_pie["Consumo"].sum() == 0:
            st.info("No hay datos suficientes para la torta.")
        else:
            total = df_pie["Consumo"].sum()
            df_pie["pct"] = (df_pie["Consumo"] / total) * 100
            df_pie["Consumo_fmt"] = df_pie["Consumo"].map(lambda x: f"{x:,.2f} MWh")
            df_pie["pct_fmt"] = df_pie["pct"].map(lambda x: f"{x:.1f}%")

            fig_pie = px.pie(
                df_pie,
                values="Consumo",
                names="SetorIndustrial",
                hole=0.55,
            )

            # Nombres SOLO en la tarjeta (hover)
            fig_pie.update_traces(
                customdata=df_pie[["Consumo_fmt", "pct_fmt"]].to_numpy(),
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "%{customdata[0]}<br>"
                    "(%{customdata[1]})"
                    "<extra></extra>"
                ),
                textinfo="none"
            )
            fig_pie.update_layout(showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

            with st.expander("Sectores detalles"):
                st.dataframe(
                    df_pie[["SetorIndustrial", "Consumo", "pct"]]
                    .rename(columns={
                        "SetorIndustrial": "Sector",
                        "Consumo": "Consumo (MWh)",
                        "pct": "% participación"
                    })
                    .style.format({
                        "Consumo (MWh)": "{:,.2f}",
                        "% participación": "{:.1f}%"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

    st.markdown("---")

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("#### Consumo total por año")
        df_bar = df_region.groupby("Ano", as_index=False)["Consumo"].sum()
        fig_bar = px.bar(df_bar, x="Ano", y="Consumo", text_auto=".2s")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col4:
        st.markdown("#### Dispersión temporal del consumo")
        fig_scatter = px.scatter(
            df_region,
            x="DataExcel",
            y="Consumo",
            color="SetorIndustrial",
            hover_data=["Regiao"]
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# ============================
# SECCIÓN 3: MAPA TIPO BRASIL (choropleth)
# ============================
st.subheader("🔥 Mapa de calor en Brasil (por ubicación)")

# IMPORTANTE:
# - Este mapa requiere que tus datos tengan una columna que coincida con el GeoJSON.
# - Con tu dataset actual, normalmente "Regiao" es macro-región, pero el geojson suele ser por estado (UF).
# - Si NO tienes columna de estado (UF), solo podrás mapear por 5 macro-regiones con un geojson de macro-regiones.

# Asumimos que tienes una columna en df llamada "UF" o "Estado" (ajústala aquí)
COL_LOCATION = os.getenv("MAP_LOCATION_COL", "UF")  # cambia a "Estado" si así viene

if COL_LOCATION not in df.columns:
    st.warning(
        f"No puedo dibujar el mapa tipo Brasil porque NO existe la columna '{COL_LOCATION}' en tus datos.\n\n"
        "Soluciones:\n"
        "1) Cambia MAP_LOCATION_COL a una columna real (ej: Estado/UF).\n"
        "2) O usa un GeoJSON por macro-regiones y mapea por 'Regiao'."
    )
else:
    try:
        geojson = load_geojson(GEOJSON_PATH)

        # Agregado por ubicación (y filtros de sector si quieres)
        df_map = df.copy()
        if sector_sel != "(Todos)":
            df_map = df_map[df_map["SetorIndustrial"] == sector_sel]

        df_map = df_map.groupby(COL_LOCATION, as_index=False)["Consumo"].sum()
        df_map = df_map.rename(columns={COL_LOCATION: "loc"})

        # Bins (estilo leyenda por rangos como el ejemplo)
        # Ajusta límites según tu escala real (aquí uso cuantiles para que se vea bien)
        if df_map["Consumo"].sum() == 0 or df_map.empty:
            st.info("No hay datos suficientes para el mapa.")
        else:
            q = df_map["Consumo"].quantile([0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1]).values
            q = sorted(set([float(x) for x in q]))
            if len(q) < 4:
                # pocos valores -> continuo
                color_args = dict(color_continuous_scale="Viridis")
            else:
                # discreto por bins
                df_map["bin"] = pd.cut(df_map["Consumo"], bins=q, include_lowest=True)
                color_args = dict(color="bin", color_discrete_sequence=px.colors.sequential.Viridis)

            # Mapa (sin labels, y el detalle en hover)
            # Para mapear: featureidkey debe coincidir con GEOJSON_KEY
            if "bin" in df_map.columns:
                fig_map = px.choropleth(
                    df_map,
                    geojson=geojson,
                    locations="loc",
                    featureidkey=GEOJSON_KEY,
                    scope="south america",
                    **color_args,
                    hover_name="loc",
                    hover_data={"Consumo": ":,.2f"},
                )
                # Hover tipo tarjeta
                fig_map.update_traces(
                    hovertemplate="<b>%{hovertext}</b><br>Consumo: %{customdata[0]:,.2f} MWh<extra></extra>"
                )
            else:
                fig_map = px.choropleth(
                    df_map,
                    geojson=geojson,
                    locations="loc",
                    featureidkey=GEOJSON_KEY,
                    scope="south america",
                    color="Consumo",
                    color_continuous_scale="Viridis",
                    hover_name="loc",
                    hover_data={"Consumo": ":,.2f"},
                )

            fig_map.update_geos(
                fitbounds="locations",
                visible=False
            )
            fig_map.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=True
            )

            st.plotly_chart(fig_map, use_container_width=True)

            with st.expander("Ver datos usados para el mapa"):
                st.dataframe(df_map, use_container_width=True)

    except FileNotFoundError:
        st.error(f"No encontré el GeoJSON en: {GEOJSON_PATH}. Colócalo ahí o ajusta GEOJSON_PATH.")
    except Exception as e:
        st.error("Error construyendo el mapa tipo Brasil.")
        st.exception(e)

st.markdown("---")

# ============================
# SECCIÓN 4: DESCARGA
# ============================
st.subheader("📥 Descargar datos filtrados")

if not df_region.empty:
    st.download_button(
        "Descargar CSV",
        df_region.to_csv(index=False).encode("utf-8"),
        file_name=f"datos_{region_sel}.csv",
        mime="text/csv"
    )
else:
    st.info("No hay datos para descargar.")

# ============================
# SECCIÓN 5: QR
# ============================
st.subheader("🔳 Abrir dashboard desde el celular")

qr = generar_qr(DASHBOARD_URL)
st.image(qr, width=220)
st.download_button("Descargar QR", qr, "dashboard_qr.png", "image/png")

st.success("✅ Dashboard cargado correctamente.")
