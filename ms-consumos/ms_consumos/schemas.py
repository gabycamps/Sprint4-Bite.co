from pydantic import BaseModel
from datetime import datetime

class ConsumoEntrada(BaseModel):
    proyecto_id: str
    proveedor: str
    servicio: str
    costo: float
    fecha: datetime