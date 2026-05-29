import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import random

MONGO_URL = "mongodb://localhost:27017"
cliente = AsyncIOMotorClient(MONGO_URL)
db = cliente["ms_consumos_db"]
coleccion = db["consumos"]

PROVEEDORES = ["AWS", "GCP"]
SERVICIOS = ["EC2", "S3", "RDS", "Lambda", "CloudStorage", "BigQuery"]
PROYECTOS = [f"proyecto-{i}" for i in range(1, 11)]

async def poblar():
    documentos = []
    fecha_base = datetime(2024, 1, 1)
    
    for i in range(10000):
        fecha = fecha_base + timedelta(days=random.randint(0, 364))
        costo = round(random.uniform(5.0, 500.0), 2)
        
        doc = {
            "proyecto_id": random.choice(PROYECTOS),
            "proveedor": random.choice(PROVEEDORES),
            "servicio": random.choice(SERVICIOS),
            "costo": costo,
            "fecha": fecha,
            "totales": {
                "dia": fecha.strftime("%Y-%m-%d"),
                "mes": fecha.strftime("%Y-%m"),
                "costo_total_dia": costo,
                "costo_total_mes": costo
            }
        }
        documentos.append(doc)
    
    await coleccion.insert_many(documentos)
    print(f" Se insertaron {len(documentos)} registros en MongoDB")

asyncio.run(poblar())