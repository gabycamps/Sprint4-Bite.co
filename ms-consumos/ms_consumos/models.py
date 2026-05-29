from datetime import datetime

def nuevo_consumo(proyecto_id: str, proveedor: str, 
                  servicio: str, costo: float, fecha: datetime) -> dict:
    return {
        "proyecto_id": proyecto_id,
        "proveedor": proveedor,
        "servicio": servicio,
        "costo": costo,
        "fecha": fecha,
        "totales": {
            "dia": fecha.strftime("%Y-%m-%d"),
            "mes": fecha.strftime("%Y-%m"),
            "costo_total_dia": costo,
            "costo_total_mes": costo
        }
    }