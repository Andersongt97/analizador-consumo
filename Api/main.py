from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importa routers (módulos) con endpoints
from routes import catalogos, consumo_actual, consumo_historico

# Crea la aplicación FastAPI
app = FastAPI(title="API Consumo Energético Ampliada")

# CORS: permite que el frontend (Streamlit u otro) consuma la API
# allow_origins=["*"] => permite cualquier origen (útil en dev, cuidado en prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conecta los routers al app con prefijos:
# /catalogos/*, /consumo/*
app.include_router(catalogos.router, prefix="/catalogos")
app.include_router(consumo_actual.router, prefix="/consumo")
app.include_router(consumo_historico.router, prefix="/consumo")

# Endpoint base para verificar estado
@app.get("/")
def root():
    return {"mensaje": "API Energética Ampliada Activa ✅"}
