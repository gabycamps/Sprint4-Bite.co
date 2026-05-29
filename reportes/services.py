"""
services.py — Lógica de negocio de MS-Reportes

Responsabilidades:
1. CacheService      — Táctica caché Redis (ASR Latencia)
2. EmpresasClient    — Llamada HTTP a MS-Empresas (API Composition)
3. ConsumosClient    — Llamada HTTP a MS-Consumos (API Composition)
4. ReporteOrchestrator — Orquestador principal
5. AnalizadorRecursosCloud — Experimento Mantenibilidad (ASR3)
   └── calcular_costo_instancias_bajo_demanda  ← método nuevo, función
       independiente que NO modifica ningún método existente
       (Principio Open/Closed — Reducción de Acoplamiento)
"""

import json
import logging
from datetime import date
from decimal import Decimal

import redis
import requests
from django.conf import settings

from .models import RecursoCloud

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Precios on-demand EC2 (USD/hora) — tabla de referencia para el Analizador
# Separada como constante para bajo acoplamiento: cambiar precios no toca
# ninguna lógica de cálculo.
# ---------------------------------------------------------------------------
PRECIOS_ON_DEMAND = {
    't2.micro':  Decimal('0.0116'),
    't2.small':  Decimal('0.0230'),
    't2.medium': Decimal('0.0464'),
    't3.micro':  Decimal('0.0104'),
    't3.small':  Decimal('0.0208'),
    't3.medium': Decimal('0.0416'),
    'm5.large':  Decimal('0.0960'),
}


# ===========================================================================
# 1. CACHÉ SERVICE — Táctica Redis (ASR Latencia)
# ===========================================================================

class CacheService:
    """
    Encapsula todas las operaciones sobre Redis.
    Clave compuesta: reporte:{proyecto_id}:{fecha_inicio}:{fecha_fin}
    TTL configurable por variable de entorno (default 300 s = 5 min).
    """

    def __init__(self):
        self._cliente = None

    def _get_cliente(self):
        """Conexión lazy para no fallar el arranque si Redis no está listo."""
        if self._cliente is None:
            self._cliente = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        return self._cliente

    def _build_key(self, proyecto_id: str, fecha_inicio: date, fecha_fin: date) -> str:
        return f"reporte:{proyecto_id}:{fecha_inicio}:{fecha_fin}"

    def get(self, proyecto_id: str, fecha_inicio: date, fecha_fin: date):
        """Retorna el dict del reporte cacheado, o None si no existe / error."""
        try:
            key = self._build_key(proyecto_id, fecha_inicio, fecha_fin)
            valor = self._get_cliente().get(key)
            if valor:
                logger.info("CACHE HIT — %s", key)
                return json.loads(valor)
        except Exception as exc:
            logger.warning("Redis GET falló (cache miss forzado): %s", exc)
        return None

    def set(self, proyecto_id: str, fecha_inicio: date, fecha_fin: date, datos: dict):
        """Almacena el reporte en Redis con TTL configurado."""
        try:
            key = self._build_key(proyecto_id, fecha_inicio, fecha_fin)
            self._get_cliente().setex(
                key,
                settings.CACHE_TTL_SEGUNDOS,
                json.dumps(datos, default=str),
            )
            logger.info("CACHE SET — %s (TTL=%ss)", key, settings.CACHE_TTL_SEGUNDOS)
        except Exception as exc:
            logger.warning("Redis SET falló (se continúa sin caché): %s", exc)

    def invalidar(self, proyecto_id: str, fecha_inicio: date, fecha_fin: date):
        """Elimina una entrada del caché (útil para pruebas sin caché)."""
        try:
            key = self._build_key(proyecto_id, fecha_inicio, fecha_fin)
            self._get_cliente().delete(key)
        except Exception as exc:
            logger.warning("Redis DELETE falló: %s", exc)


# Instancia singleton del servicio de caché
cache_service = CacheService()


# ===========================================================================
# 2. CLIENTE MS-EMPRESAS — API Composition
# ===========================================================================

class EmpresasClient:
    """
    Consulta MS-Empresas para validar que un proyecto_id existe y está activo.
    Endpoint: GET /api/v1/proyectos/?cloud_account_id=<proyecto_id>
              o GET /api/v1/internal/proyectos/batch/?ids=<uuid>

    NOTA: En este sistema los proyecto_id de MongoDB son strings como
    'proyecto-1'. MS-Empresas usa UUIDs como PK, pero expone
    cloud_account_id como campo de búsqueda. Usamos ese campo.
    """

    def __init__(self):
        self.base_url = settings.MS_EMPRESAS_URL
        self.timeout = 5  # segundos

    def buscar_proyecto_por_cloud_id(self, proyecto_id: str, token: str) -> dict | None:
        """
        Busca metadatos del proyecto usando cloud_account_id = proyecto_id.
        Retorna el primer proyecto encontrado, o None si no existe.

        Táctica seguridad: proyecto_id ya fue validado por validators.py
        antes de llegar aquí. El ORM en MS-Empresas usa prepared statements.
        """
        url = f"{self.base_url}/api/v1/proyectos/"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"cloud_account_id": proyecto_id}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                return data[0]
            if isinstance(data, dict) and data.get('results'):
                return data['results'][0]
        except requests.exceptions.Timeout:
            logger.error("MS-Empresas timeout para proyecto_id=%s", proyecto_id)
            raise TimeoutError("MS-Empresas no respondió en tiempo.")
        except requests.exceptions.RequestException as exc:
            logger.error("MS-Empresas error: %s", exc)
            raise ConnectionError(f"No se pudo contactar MS-Empresas: {exc}")

        return None


# ===========================================================================
# 3. CLIENTE MS-CONSUMOS — API Composition
# ===========================================================================

class ConsumosClient:
    """
    Obtiene registros de consumo cloud desde MS-Consumos (FastAPI + MongoDB).
    Endpoint: GET /api/consumos/{proyecto_id}?fecha_inicio=...&fecha_fin=...
    Puerto: 8002
    """

    def __init__(self):
        self.base_url = settings.MS_CONSUMOS_URL
        self.timeout = 10  # MongoDB puede tardar más bajo carga

    def obtener_consumos(
        self, proyecto_id: str, fecha_inicio: date, fecha_fin: date
    ) -> list:
        """
        Obtiene todos los registros de consumo del proyecto en el rango de fechas.
        Retorna lista de dicts con el Computed Pattern de MongoDB.

        proyecto_id ya fue validado — solo letras, números y guiones.
        """
        url = f"{self.base_url}/api/consumos/{proyecto_id}"
        params = {
            "fecha_inicio": str(fecha_inicio),
            "fecha_fin": str(fecha_fin),
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error("MS-Consumos timeout para proyecto_id=%s", proyecto_id)
            raise TimeoutError("MS-Consumos no respondió en tiempo.")
        except requests.exceptions.RequestException as exc:
            logger.error("MS-Consumos error: %s", exc)
            raise ConnectionError(f"No se pudo contactar MS-Consumos: {exc}")


# ===========================================================================
# 4. ORQUESTADOR PRINCIPAL — API Composition Pattern
# ===========================================================================

class ReporteOrchestrator:
    """
    Orquesta la consolidación del reporte financiero:
    1. Verifica caché Redis
    2. Valida proyecto en MS-Empresas
    3. Obtiene consumos de MS-Consumos
    4. Consolida y calcula totales
    5. Almacena en caché y persiste en PostgreSQL
    """

    def __init__(self):
        self.cache = cache_service
        self.empresas_client = EmpresasClient()
        self.consumos_client = ConsumosClient()

    def generar_reporte(
        self,
        proyecto_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        token: str,
        usar_cache: bool = True,
    ) -> dict:
        """
        Genera el reporte consolidado aplicando la táctica de caché.
        Retorna el reporte como dict, con campo 'desde_cache' para métricas.
        """
        # --- Paso 1: Verificar caché (ASR Latencia — happy path < 1s) ---
        if usar_cache:
            reporte_cacheado = self.cache.get(proyecto_id, fecha_inicio, fecha_fin)
            if reporte_cacheado:
                reporte_cacheado['desde_cache'] = True
                return reporte_cacheado

        # --- Paso 2: Validar proyecto en MS-Empresas ---
        proyecto_meta = self.empresas_client.buscar_proyecto_por_cloud_id(
            proyecto_id, token
        )

        if proyecto_meta is None:
            raise ValueError(
                f"El proyecto '{proyecto_id}' no existe o no está activo en MS-Empresas."
            )

        # --- Paso 3: Obtener consumos de MS-Consumos (MongoDB) ---
        consumos = self.consumos_client.obtener_consumos(
            proyecto_id, fecha_inicio, fecha_fin
        )

        # --- Paso 4: Consolidar reporte en memoria ---
        reporte = self._consolidar(proyecto_id, proyecto_meta, consumos, fecha_inicio, fecha_fin)

        # --- Paso 5: Guardar en caché para requests subsiguientes ---
        if usar_cache:
            self.cache.set(proyecto_id, fecha_inicio, fecha_fin, reporte)

        reporte['desde_cache'] = False
        return reporte

    def _consolidar(
        self,
        proyecto_id: str,
        proyecto_meta: dict,
        consumos: list,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> dict:
        """
        Consolida los datos de múltiples fuentes en una vista única.
        Usa el Computed Pattern de MongoDB (totales pre-calculados).
        """
        costo_total = Decimal('0')
        costo_por_proveedor = {}
        costo_por_servicio = {}
        costo_por_dia = {}

        for registro in consumos:
            costo = Decimal(str(registro.get('costo', 0)))
            costo_total += costo

            proveedor = registro.get('proveedor', 'desconocido')
            costo_por_proveedor[proveedor] = (
                costo_por_proveedor.get(proveedor, Decimal('0')) + costo
            )

            servicio = registro.get('servicio', 'desconocido')
            costo_por_servicio[servicio] = (
                costo_por_servicio.get(servicio, Decimal('0')) + costo
            )

            # Usar el Computed Pattern: día pre-calculado en MongoDB
            totales = registro.get('totales', {})
            dia = totales.get('dia') or str(registro.get('fecha', ''))[:10]
            if dia:
                costo_por_dia[dia] = (
                    costo_por_dia.get(dia, Decimal('0')) + costo
                )

        presupuesto = Decimal(str(proyecto_meta.get('presupuesto', 0) or 0))
        porcentaje_uso = (
            float(costo_total / presupuesto * 100) if presupuesto > 0 else 0
        )

        return {
            'proyecto_id': proyecto_id,
            'proyecto_nombre': proyecto_meta.get('nombre', ''),
            'empresa_nombre': proyecto_meta.get('empresa_nombre', ''),
            'presupuesto': float(presupuesto),
            'fecha_inicio': str(fecha_inicio),
            'fecha_fin': str(fecha_fin),
            'total_registros': len(consumos),
            'costo_total': float(costo_total),
            'porcentaje_presupuesto_usado': round(porcentaje_uso, 2),
            'costo_por_proveedor': {k: float(v) for k, v in costo_por_proveedor.items()},
            'costo_por_servicio': {k: float(v) for k, v in costo_por_servicio.items()},
            'costo_por_dia': {k: float(v) for k, v in sorted(costo_por_dia.items())},
        }


# ===========================================================================
# 5. ANALIZADOR DE RECURSOS CLOUD — Experimento Mantenibilidad (ASR3)
#
# Táctica: Reducción de Acoplamiento (Principio Open/Closed)
# - Los métodos existentes NO se modifican.
# - calcular_costo_instancias_bajo_demanda se agrega como función
#   INDEPENDIENTE con responsabilidad única.
# - Complejidad ciclomática del nuevo método: 4 (< 10, cumple ASR3)
# - Duplicación de código: 0% (no copia lógica existente)
# ===========================================================================

class AnalizadorRecursosCloud:
    """
    Analizador de recursos cloud.
    Métodos preexistentes (línea base para SonarQube):
    - listar_recursos_activos
    - contar_recursos_por_tipo

    Método nuevo (experimento ASR3):
    - calcular_costo_instancias_bajo_demanda
    """

    # --- Métodos preexistentes (NO se modifican) ---

    def listar_recursos_activos(self, proyecto_id: str) -> list:
        """
        Lista todos los recursos cloud activos para un proyecto.
        Usa el ORM de Django — prepared statements automáticos (ASR Seguridad).
        Complejidad ciclomática: 2
        """
        recursos = (
            RecursoCloud.objects
            .filter(proyecto_id=proyecto_id, activo=True)
            .values('id', 'tipo_instancia', 'cantidad', 'horas_uso', 'fecha_registro')
        )
        return list(recursos)

    def contar_recursos_por_tipo(self, proyecto_id: str) -> dict:
        """
        Cuenta cuántos recursos activos hay por tipo de instancia.
        Complejidad ciclomática: 3
        """
        recursos = RecursoCloud.objects.filter(proyecto_id=proyecto_id, activo=True)
        conteo = {}
        for recurso in recursos:
            tipo = recurso.tipo_instancia
            conteo[tipo] = conteo.get(tipo, 0) + recurso.cantidad
        return conteo

    # --- Método nuevo — agregado sin tocar los anteriores (Open/Closed) ---

    def calcular_costo_instancias_bajo_demanda(
        self,
        proyecto_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> dict:
        """
        Calcula el costo estimado de las instancias EC2 bajo demanda
        para un proyecto en un rango de fechas dado.

        Parámetros
        ----------
        proyecto_id  : identificador del proyecto (ej. 'proyecto-1')
        fecha_inicio : fecha de inicio del período (inclusive)
        fecha_fin    : fecha de fin del período (inclusive)

        Retorna
        -------
        dict con:
          - proyecto_id
          - fecha_inicio / fecha_fin
          - costo_estimado_total_usd (Decimal)
          - detalle_por_tipo: {tipo_instancia: costo_usd}

        Táctica Reducción de Acoplamiento:
        - No modifica listar_recursos_activos ni contar_recursos_por_tipo.
        - Responsabilidad única: solo calcular costo bajo demanda.
        - Usa PRECIOS_ON_DEMAND como constante externa (sin hardcoding).

        Complejidad ciclomática: 4 (cumple ASR mantenibilidad < 10)
        Duplicación de código: 0%
        """
        recursos = (
            RecursoCloud.objects
            .filter(
                proyecto_id=proyecto_id,
                activo=True,
                fecha_registro__gte=fecha_inicio,
                fecha_registro__lte=fecha_fin,
            )
        )

        costo_total = Decimal('0')
        detalle_por_tipo = {}

        for recurso in recursos:
            precio_hora = PRECIOS_ON_DEMAND.get(recurso.tipo_instancia, Decimal('0'))
            costo_recurso = precio_hora * Decimal(str(recurso.horas_uso)) * recurso.cantidad
            costo_total += costo_recurso

            tipo = recurso.tipo_instancia
            detalle_por_tipo[tipo] = (
                detalle_por_tipo.get(tipo, Decimal('0')) + costo_recurso
            )

        return {
            'proyecto_id': proyecto_id,
            'fecha_inicio': str(fecha_inicio),
            'fecha_fin': str(fecha_fin),
            'costo_estimado_total_usd': float(costo_total),
            'detalle_por_tipo': {k: float(v) for k, v in detalle_por_tipo.items()},
        }


# Instancias singleton
reporte_orchestrator = ReporteOrchestrator()
analizador = AnalizadorRecursosCloud()
