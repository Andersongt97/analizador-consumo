import os
import json
from io import BytesIO

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import qrcode

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import inch

# ============================
# CONFIGURACIÓN GENERAL
# ============================
# URL base del backend (FastAPI)
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# URL “pública” del dashboard para incrustar en QR (idealmente IP/LAN o dominio)
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501")

# Rutas/llaves para el GeoJSON del mapa
GEOJSON_PATH = os.getenv("GEOJSON_PATH", "data/br_states.geojson")
GEOJSON_KEY = os.getenv("GEOJSON_KEY", "properties.sigla")

# Template (tema) de plotly
TEMPLATE = "plotly_white"
SEQ = px.colors.qualitative.Set2
SEQ2 = px.colors.qualitative.Safe

# ============================
# UNIDADES (AQUÍ DEFINES MWh/GWh)
# ============================
# El Excel/API entrega típicamente MWh. Si quieres mostrar en GWh, conviertes.
UNIDAD_ORIGEN = "MWh"
MOSTRAR_EN_GWH = True


def to_gwh(valor_mwh: float) -> float:
    """Convierte un valor en MWh a GWh."""
    return valor_mwh / 1000.0


def energia_display_series(series: pd.Series) -> pd.Series:
    """
    Convierte una Serie de consumo para visualización.
    - Si MOSTRAR_EN_GWH = True => divide entre 1000
    - Si False => se deja tal cual
    """
    if MOSTRAR_EN_GWH:
        return series / 1000.0
    return series


def unidad_txt() -> str:
    """Texto de la unidad que verá el usuario en el dashboard."""
    return "GWh" if MOSTRAR_EN_GWH else UNIDAD_ORIGEN


def fmt_energia(valor_mwh: float) -> str:
    """
    Formatea un número de consumo.
    Nota: el valor “base” que llega es MWh, por eso se convierte aquí si aplica.
    """
    if MOSTRAR_EN_GWH:
        return f"{to_gwh(valor_mwh):,.2f} GWh"
    return f"{valor_mwh:,.2f} {UNIDAD_ORIGEN}"


# ============================
# CONFIG STREAMLIT
# ============================
st.set_page_config(page_title="Dashboard Energético Brasil", layout="wide")

# Estilo en modo oscuro (CSS embebido)
st.markdown(
    """
<style>
.stApp { background-color: #2F2F31; }
div[data-testid="stMetric"] {
    background: #3b3b3f;
    padding: 14px;
    border-radius: 14px;
    border: 1px solid #5a5a60;
}
h1, h2, h3, h4, h5, h6 { color: #f4f4f5; }
div, p, span, label { color: #e5e7eb; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Dashboard de Consumo Energético por Región - Brasil")
st.caption("Backend: FastAPI • Frontend: Streamlit • Datos: Excel oficial por regiones")

# ============================
# FUNCIONES AUXILIARES (API)
# ============================
@st.cache_data
def get_regiones():
    """Trae el catálogo de regiones desde el backend."""
    resp = requests.get(f"{API_URL}/catalogos/regioes", timeout=30)
    resp.raise_for_status()
    return resp.json()["regioes"]


@st.cache_data
def get_setores():
    """Trae el catálogo de sectores industriales desde el backend."""
    resp = requests.get(f"{API_URL}/catalogos/setores-industriais", timeout=30)
    resp.raise_for_status()
    return resp.json()["setores"]


@st.cache_data
def get_datos_industrial():
    """
    Trae TODOS los registros crudos industriales del backend.
    Esto alimenta la tabla, filtros y visualizaciones en Streamlit.
    """
    resp = requests.get(f"{API_URL}/consumo/datos-industrial", timeout=60)
    resp.raise_for_status()
    return resp.json()


# ============================
# FUNCIONES AUXILIARES (GeoJSON)
# ============================
@st.cache_data
def load_geojson(path: str):
    """Carga el GeoJSON desde disco (para el mapa coroplético)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================
# FUNCIONES AUXILIARES (QR)
# ============================
def generar_qr(url: str) -> bytes:
    """Genera un QR (PNG) en memoria apuntando a una URL."""
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================
# FUNCIONES AUXILIARES (PDF)
# ============================
def fig_to_png_bytes(fig, scale=2) -> bytes:
    """
    Convierte una figura Plotly a PNG en bytes.
    Requiere kaleido instalado para fig.to_image().
    """
    return fig.to_image(format="png", scale=scale)


def build_pdf_report(titulo: str, filtros: dict, figs: list, tabla_df=None) -> bytes:
    """
    Construye un PDF multipágina:
    - Página 1: título + filtros + cantidad de registros
    - Páginas siguientes: una gráfica por página
    Devuelve el PDF como bytes listo para st.download_button.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ---- Portada / Resumen de filtros ----
    y = height - 0.8 * inch
    c.setFont("Helvetica-Bold", 16)
    c.drawString(0.8 * inch, y, titulo)

    y -= 0.4 * inch
    c.setFont("Helvetica", 10)
    c.drawString(0.8 * inch, y, "Filtros aplicados:")
    y -= 0.2 * inch

    for k, v in filtros.items():
        c.drawString(1.0 * inch, y, f"- {k}: {v}")
        y -= 0.18 * inch

    if tabla_df is not None and not tabla_df.empty:
        y -= 0.1 * inch
        c.drawString(0.8 * inch, y, f"Registros incluidos: {len(tabla_df):,}")
        y -= 0.3 * inch

    c.showPage()

    # ---- Una página por figura ----
    for idx, (name, fig) in enumerate(figs, start=1):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.8 * inch, height - 0.8 * inch, f"{idx}. {name}")

        img_bytes = fig_to_png_bytes(fig, scale=2)
        img = ImageReader(BytesIO(img_bytes))

        # Caja de imagen en la página
        img_w = width - 1.6 * inch
        img_h = 6.2 * inch
        x0 = 0.8 * inch
        y0 = height - 1.2 * inch - img_h

        c.drawImage(
            img,
            x0,
            y0,
            width=img_w,
            height=img_h,
            preserveAspectRatio=True,
            anchor="c",
        )
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ============================
# CARGA DE DATOS (desde la API)
# ============================
try:
    # Catálogos (sidebar)
    regiones = get_regiones()
    setores_api = get_setores()

    # Datos crudos
    data = get_datos_industrial()
    df = pd.DataFrame(data)

    # Normalizaciones típicas para evitar errores de tipo
    if "DataExcel" in df.columns:
        df["DataExcel"] = pd.to_datetime(df["DataExcel"], errors="coerce")
    if "Consumo" in df.columns:
        df["Consumo"] = pd.to_numeric(df["Consumo"], errors="coerce").fillna(0)

except Exception as e:
    # Si falla la API o el formato, el dashboard se detiene
    st.error("No se pudo conectar a la API o cargar los datos.")
    st.exception(e)
    st.stop()


# ============================
# SIDEBAR (FILTROS)
# ============================
st.sidebar.header("Filtros")

# Filtro por región (o todas)
region_sel = st.sidebar.selectbox("Seleccione una región:", ["(Todas)"] + regiones)

# Filtro por sector (une sectores detectados en datos + catálogo API)
sectores_df = (
    sorted(df["SetorIndustrial"].dropna().unique().tolist())
    if "SetorIndustrial" in df.columns
    else []
)
sectores = sorted(set(setores_api) | set(sectores_df))
sector_sel = st.sidebar.selectbox("Filtrar por sector:", ["(Todos)"] + sectores)

# Filtro por rango de fechas
if "DataExcel" in df.columns and df["DataExcel"].notna().any():
    min_date = df["DataExcel"].min().date()
    max_date = df["DataExcel"].max().date()
    date_range = st.sidebar.date_input("Rango de fechas:", (min_date, max_date))
else:
    date_range = None


# ============================
# FILTRADO PRINCIPAL (aplica filtros a df)
# ============================
df_filtrado = df.copy()

if region_sel != "(Todas)" and "Regiao" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Regiao"] == region_sel]

if sector_sel != "(Todos)" and "SetorIndustrial" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["SetorIndustrial"] == sector_sel]

if date_range and "DataExcel" in df_filtrado.columns:
    d1, d2 = date_range
    df_filtrado = df_filtrado[
        (df_filtrado["DataExcel"].dt.date >= d1) & (df_filtrado["DataExcel"].dt.date <= d2)
    ]


# ============================
# SECCIÓN 1: TABLA + KPIs + ESTADÍSTICAS
# ============================
colA, colB, colC = st.columns([2, 1, 1])

with colA:
    st.subheader("📋 Datos filtrados")
    st.dataframe(df_filtrado, width="stretch", height=320)

with colB:
    st.subheader("📌 KPIs")
    st.metric("Registros", f"{len(df_filtrado):,}")
    if "Consumo" in df_filtrado.columns:
        st.metric("Consumo total", fmt_energia(float(df_filtrado["Consumo"].sum())))

with colC:
    st.subheader(f"📉 Estadísticas (Consumo en {unidad_txt()})")
    if "Consumo" in df_filtrado.columns and not df_filtrado.empty:
        s = df_filtrado["Consumo"].dropna()
        if len(s) > 0:
            media = float(s.mean())
            mediana = float(s.median())
            std = float(s.std())
            minimo = float(s.min())
            maximo = float(s.max())

            cC1, cC2 = st.columns(2)
            cC1.metric("Media", fmt_energia(media))
            cC2.metric("Mediana", fmt_energia(mediana))

            cC3, cC4 = st.columns(2)
            cC3.metric("Desv. Estándar", fmt_energia(std))
            cC4.metric("Mínimo", fmt_energia(minimo))

            st.metric("Máximo", fmt_energia(maximo))
        else:
            st.info("No hay valores numéricos para calcular estadísticas.")
    else:
        st.info("No hay datos para estadísticas.")


# ============================
# SECCIÓN 2: GRÁFICAS
# ============================
st.subheader("Visualizaciones")

fig_barras = None
fig_pie = None
fig_hist = None
fig_scatter = None
fig_map = None

c1, c2 = st.columns(2)

with c1:
    # Barras: consumo por sector
    if (
        not df_filtrado.empty
        and "SetorIndustrial" in df_filtrado.columns
        and "Consumo" in df_filtrado.columns
    ):
        df_bar = (
            df_filtrado.groupby("SetorIndustrial", as_index=False)["Consumo"]
            .sum()
            .sort_values("Consumo", ascending=False)
        )

        # Conversión visual (GWh si aplica)
        df_bar_plot = df_bar.copy()
        df_bar_plot["Consumo"] = energia_display_series(df_bar_plot["Consumo"])

        fig_barras = px.bar(
            df_bar_plot,
            x="SetorIndustrial",
            y="Consumo",
            color="SetorIndustrial",
            color_discrete_sequence=SEQ,
            title=f"Consumo por Sector Industrial ({unidad_txt()})",
            template=TEMPLATE,
        )
        fig_barras.update_layout(showlegend=False)
        fig_barras.update_yaxes(title_text=f"Consumo ({unidad_txt()})")
        st.plotly_chart(fig_barras, width="stretch")
    else:
        st.info("No hay datos para gráfica de barras.")

with c2:
    # Torta + tarjetas: distribución del consumo
    if not df_filtrado.empty and "Consumo" in df_filtrado.columns:
        if region_sel == "(Todas)":
            # Si no filtras región, la torta es por región
            if "Regiao" in df_filtrado.columns:
                df_pie = df_filtrado.groupby("Regiao", as_index=False)["Consumo"].sum()
                df_pie = df_pie.sort_values("Consumo", ascending=False).reset_index(drop=True)

                df_pie_plot = df_pie.copy()
                df_pie_plot["Consumo"] = energia_display_series(df_pie_plot["Consumo"])

                fig_pie = px.pie(
                    df_pie_plot,
                    names="Regiao",
                    values="Consumo",
                    color="Regiao",
                    color_discrete_sequence=SEQ2,
                    title=f"Distribución de consumo por Región ({unidad_txt()})",
                    template=TEMPLATE,
                )
                # Se oculta texto en la torta y se muestra el detalle en tarjetas
                fig_pie.update_traces(textinfo="none")
                st.plotly_chart(fig_pie, width="stretch")

                st.markdown("#### 📌 Detalle por Región (tarjetas)")
                total_mwh = float(df_pie["Consumo"].sum()) if not df_pie.empty else 0

                cols_cards = st.columns(3)
                for i, row in df_pie.iterrows():
                    nombre = str(row["Regiao"])
                    consumo_mwh = float(row["Consumo"])
                    pct = (consumo_mwh / total_mwh * 100) if total_mwh > 0 else 0
                    with cols_cards[i % 3]:
                        st.metric(
                            label=nombre,
                            value=fmt_energia(consumo_mwh),
                            delta=f"{pct:.2f}% del total",
                        )
            else:
                st.info("No existe la columna 'Regiao' para construir la torta por región.")
        else:
            # Si filtras región, la torta es por sector dentro de esa región
            if "SetorIndustrial" in df_filtrado.columns:
                df_pie_reg = df_filtrado.groupby("SetorIndustrial", as_index=False)["Consumo"].sum()
                df_pie_reg = df_pie_reg.sort_values("Consumo", ascending=False).reset_index(drop=True)

                df_pie_reg_plot = df_pie_reg.copy()
                df_pie_reg_plot["Consumo"] = energia_display_series(df_pie_reg_plot["Consumo"])

                fig_pie = px.pie(
                    df_pie_reg_plot,
                    names="SetorIndustrial",
                    values="Consumo",
                    color="SetorIndustrial",
                    color_discrete_sequence=SEQ,
                    title=f"Distribución de consumo por Sector en {region_sel} ({unidad_txt()})",
                    template=TEMPLATE,
                )
                fig_pie.update_traces(textinfo="none")
                st.plotly_chart(fig_pie, width="stretch")

                st.markdown(f"#### 📌 Detalle por Sector en {region_sel} (tarjetas)")
                total_mwh = float(df_pie_reg["Consumo"].sum()) if not df_pie_reg.empty else 0

                cols_cards = st.columns(3)
                for i, row in df_pie_reg.iterrows():
                    nombre = str(row["SetorIndustrial"])
                    consumo_mwh = float(row["Consumo"])
                    pct = (consumo_mwh / total_mwh * 100) if total_mwh > 0 else 0
                    with cols_cards[i % 3]:
                        st.metric(
                            label=nombre,
                            value=fmt_energia(consumo_mwh),
                            delta=f"{pct:.2f}% del total",
                        )
            else:
                st.info("No existe la columna 'SetorIndustrial' para construir la torta por sector.")
    else:
        st.info("No hay datos para gráfica de torta.")

c3, c4 = st.columns(2)

with c3:
    # Histograma del consumo
    if not df_filtrado.empty and "Consumo" in df_filtrado.columns:
        df_hist_plot = df_filtrado.copy()
        df_hist_plot["Consumo"] = energia_display_series(df_hist_plot["Consumo"])

        fig_hist = px.histogram(
            df_hist_plot,
            x="Consumo",
            nbins=30,
            title=f"Histograma del Consumo ({unidad_txt()})",
            template=TEMPLATE,
        )
        fig_hist.update_xaxes(title_text=f"Consumo ({unidad_txt()})")
        st.plotly_chart(fig_hist, width="stretch")
    else:
        st.info("No hay datos para histograma.")

with c4:
    # Scatter consumo vs fecha
    if (
        not df_filtrado.empty
        and "DataExcel" in df_filtrado.columns
        and "Consumo" in df_filtrado.columns
    ):
        df_sc = df_filtrado.dropna(subset=["DataExcel"]).sort_values("DataExcel").copy()
        df_sc["Consumo"] = energia_display_series(df_sc["Consumo"])

        fig_scatter = px.scatter(
            df_sc,
            x="DataExcel",
            y="Consumo",
            color="Regiao" if "Regiao" in df_sc.columns else None,
            color_discrete_sequence=SEQ2,
            title=f"Consumo vs Fecha ({unidad_txt()})",
            template=TEMPLATE,
        )
        fig_scatter.update_yaxes(title_text=f"Consumo ({unidad_txt()})")
        st.plotly_chart(fig_scatter, width="stretch")
    else:
        st.info("No hay datos para dispersión por fecha.")


# ============================
# SECCIÓN 3: MAPA DE CALOR (por UF)
# ============================
st.subheader("Mapa de calor en Brasil (por ubicación)")

try:
    geojson = load_geojson(GEOJSON_PATH)

    # Si faltan columnas o no hay datos, no se construye el mapa
    if df_filtrado.empty or "Regiao" not in df_filtrado.columns or "Consumo" not in df_filtrado.columns:
        st.info("No hay datos suficientes para construir el mapa.")
    else:
        # Agregación por región
        df_reg = df_filtrado.groupby("Regiao", as_index=False)["Consumo"].sum()

        # Mapeo estático de UF -> Regiao (para pintar por estado)
        uf_to_regiao = {
            "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
            "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
            "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
            "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
            "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
            "PR": "Sul", "RS": "Sul", "SC": "Sul",
        }

        # Construye DF por UF y le pega el consumo por región
        df_uf = pd.DataFrame({"UF": list(uf_to_regiao.keys()), "Regiao": list(uf_to_regiao.values())}).merge(
            df_reg, on="Regiao", how="left"
        )
        df_uf["Consumo"] = df_uf["Consumo"].fillna(0)

        # Conversión visual (GWh si aplica)
        df_uf_plot = df_uf.copy()
        df_uf_plot["Consumo"] = energia_display_series(df_uf_plot["Consumo"])

        # Coroplético por UF
        fig_map = px.choropleth(
            df_uf_plot,
            geojson=geojson,
            locations="UF",
            featureidkey=GEOJSON_KEY,
            color="Consumo",
            hover_name="UF",
            hover_data={"Regiao": True, "Consumo": ":,.2f"},
            color_continuous_scale="YlOrRd",
            scope="south america",
            template="plotly_white",
        )

        fig_map.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
        fig_map.update_layout(
            height=820,
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        fig_map.update_layout(coloraxis_colorbar_title=f"Consumo ({unidad_txt()})")

        st.plotly_chart(fig_map, width="stretch")

        with st.expander("Ver datos usados para el mapa (UF = estado)"):
            st.dataframe(df_uf_plot, width="stretch")

except FileNotFoundError:
    st.error(f"No encontré el GeoJSON en: {GEOJSON_PATH}. Ajusta GEOJSON_PATH o coloca el archivo ahí.")
except Exception as e:
    st.error("Error construyendo el mapa de calor.")
    st.exception(e)


# ============================
# SECCIÓN 4: DESCARGAS (CSV + PDF)
# ============================
st.subheader("📥 Descargar datos e informe")

colD, colE = st.columns(2)

with colD:
    # Descarga CSV con los datos filtrados
    if not df_filtrado.empty:
        st.download_button(
            "⬇️ Descargar CSV (datos filtrados)",
            df_filtrado.to_csv(index=False).encode("utf-8"),
            file_name="datos_filtrados.csv",
            mime="text/csv",
        )
    else:
        st.info("No hay datos filtrados para descargar CSV.")

with colE:
    st.write("Genera un PDF con las gráficas visibles del dashboard.")

    # Diccionario de filtros para la portada del PDF
    filtros_reporte = {
        "Región": region_sel,
        "Sector": sector_sel,
        "Fecha": f"{date_range[0]} a {date_range[1]}" if date_range else "N/A",
        "Unidad": unidad_txt(),
    }

    # Lista de figuras que se agregan al reporte si existen
    figs_reporte = []
    if fig_barras is not None:
        figs_reporte.append(("Consumo por Sector (Barras)", fig_barras))
    if fig_pie is not None:
        figs_reporte.append(("Distribución (Torta)", fig_pie))
    if fig_hist is not None:
        figs_reporte.append(("Histograma de Consumo", fig_hist))
    if fig_scatter is not None:
        figs_reporte.append(("Consumo vs Fecha (Dispersión)", fig_scatter))
    if fig_map is not None:
        figs_reporte.append(("Mapa de Calor (Brasil)", fig_map))

    if figs_reporte:
        try:
            pdf_bytes = build_pdf_report(
                titulo="Informe - Analizador de Consumo Energético",
                filtros=filtros_reporte,
                figs=figs_reporte,
                tabla_df=df_filtrado,
            )

            st.download_button(
                label="⬇️ Descargar PDF con gráficas",
                data=pdf_bytes,
                file_name="informe_consumo_energetico.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error("No se pudo generar el PDF. Revisa kaleido y reportlab.")
            st.exception(e)
    else:
        st.info("No hay figuras disponibles para incluir en el PDF (datos vacíos o filtros muy estrictos).")


# ============================
# SECCIÓN 5: QR
# ============================
st.subheader("🔳 Abrir dashboard desde el celular")

# Genera el QR con la URL definida en env (DASHBOARD_URL)
qr_bytes = generar_qr(DASHBOARD_URL)
st.image(qr_bytes, width=220)

st.success("✅ Dashboard cargado correctamente.")
