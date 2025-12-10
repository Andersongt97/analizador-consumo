from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import catalogos, consumo_actual, consumo_historico

app = FastAPI(title="API Consumo Energético Ampliada")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(catalogos.router, prefix="/catalogos")
app.include_router(consumo_actual.router, prefix="/consumo")
app.include_router(consumo_historico.router, prefix="/consumo")

@app.get("/")
def root():
    return {"mensaje": "API Energética Ampliada Activa ✅"}
