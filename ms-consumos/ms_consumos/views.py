from fastapi import APIRouter, HTTPException
from ms_consumos.schemas import ConsumoEntrada
from ms_consumos.logic import obtener_consumos, guardar_consumo
from ms_consumos.models import nuevo_consumo

router = APIRouter()

@router.get("/consumos/{proyecto_id}")
async def get_consumos(proyecto_id: str, fecha_inicio: str, fecha_fin: str):
    datos = await obtener_consumos(proyecto_id, fecha_inicio, fecha_fin)
    if not datos:
        raise HTTPException(status_code=404, detail="No hay consumos para ese proyecto")
    return datos

@router.post("/consumos/")
async def post_consumo(consumo: ConsumoEntrada):
    doc = nuevo_consumo(
        consumo.proyecto_id,
        consumo.proveedor,
        consumo.servicio,
        consumo.costo,
        consumo.fecha
    )
    id_creado = await guardar_consumo(doc)
    return {"id": id_creado, "mensaje": "Consumo creado"}