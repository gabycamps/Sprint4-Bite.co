import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
cliente = AsyncIOMotorClient(MONGO_URL)
db = cliente["ms_consumos_db"]
coleccion = db["consumos"]

async def obtener_consumos(proyecto_id: str, fecha_inicio: str, fecha_fin: str):
    query = {
        "proyecto_id": proyecto_id,
        "totales.dia": {
            "$gte": fecha_inicio,
            "$lte": fecha_fin
        }
    }
    cursor = coleccion.find(query, {"_id": 0})
    resultados = await cursor.to_list(length=10000)
    return resultados

async def guardar_consumo(documento: dict):
    resultado = await coleccion.insert_one(documento)
    return str(resultado.inserted_id)