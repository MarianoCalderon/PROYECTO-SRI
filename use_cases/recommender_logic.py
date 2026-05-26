import json
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from infrastructure import db_clients
from infrastructure.key_utils import normalizar_clave

redis_client = db_clients.redis_client
neo4j_driver = db_clients.neo4j_driver

# Nombres internos. Se conservan para depurar o auditar el modelo desde la API,
# pero el frontend muestra explicaciones humanas, no porcentajes ni términos técnicos.
COMPONENT_LABELS = {
    "content": "contenido",
    "collaborative": "colaborativo",
    "preference": "preferencias",
    "popularity": "popularidad",
}


def _limpiar_lista(valores: Optional[Iterable[str]]) -> List[str]:
    vistos = set()
    salida: List[str] = []
    for valor in valores or []:
        texto = str(valor).strip()
        clave = texto.lower()
        if texto and clave not in vistos:
            vistos.add(clave)
            salida.append(texto)
    return salida


def _float_seguro(valor: Any, default: float = 0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def _mayuscula_inicial(texto: str) -> str:
    texto = str(texto or "").strip()
    if not texto:
        return ""
    return texto[0].upper() + texto[1:]


def obtener_metadatos(track_ids: Iterable[str]) -> List[Dict[str, Any]]:
    """Recupera metadatos desde Redis preservando el orden y evitando duplicados."""
    resultados: List[Dict[str, Any]] = []
    vistos = set()

    for tid in track_ids:
        if not tid or tid in vistos:
            continue
        vistos.add(tid)
        datos = redis_client.hgetall(f"track:{tid}")
        if not datos:
            continue
        resultados.append(
            {
                "track_id": tid,
                "titulo": datos.get("titulo", "Canción Desconocida"),
                "artista": datos.get("artista", "Artista Anónimo"),
                "genero": datos.get("genero", "General"),
                "popularidad": _float_seguro(datos.get("popularidad")),
            }
        )
    return resultados


def _metadatos_uno(track_id: str) -> Optional[Dict[str, Any]]:
    datos = obtener_metadatos([track_id])
    return datos[0] if datos else None


def _titulo_track(track_id: str) -> Optional[str]:
    meta = _metadatos_uno(track_id)
    if not meta:
        return None
    titulo = str(meta.get("titulo") or "").strip()
    return titulo or None


def _vector_cancion(track_id: str) -> Optional[np.ndarray]:
    raw = redis_client.hget(f"track:{track_id}", "features")
    if not raw:
        return None
    try:
        vector = np.array(json.loads(raw), dtype="float32")
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if vector.shape != (db_clients.FAISS_DIM,):
        return None
    return vector


def _historial_usuario(user_id: str) -> List[Dict[str, Any]]:
    query = """
    MATCH (u:Usuario {id: $uid})-[r:CALIFICO]->(c:Cancion)
    RETURN c.id AS track_id,
           coalesce(r.valor, 0) AS rating,
           coalesce(r.timestamp, 0) AS timestamp,
           c.titulo AS titulo,
           c.artista AS artista,
           c.genero AS genero
    ORDER BY timestamp DESC
    """
    with neo4j_driver.session() as session:
        resultado = session.run(query, uid=user_id)
        return [
            {
                "track_id": record["track_id"],
                "rating": int(record["rating"]),
                "timestamp": int(record["timestamp"]),
                "titulo": record.get("titulo"),
                "artista": record.get("artista"),
                "genero": record.get("genero"),
            }
            for record in resultado
        ]


def _preferencias_usuario(
    user_id: str,
    initial_genres: Optional[List[str]],
    initial_artists: Optional[List[str]],
) -> Tuple[List[str], List[str]]:
    generos = _limpiar_lista(initial_genres)
    artistas = _limpiar_lista(initial_artists)

    query = """
    MATCH (u:Usuario {id: $uid})
    RETURN u.generos_favoritos AS generos,
           u.artistas_favoritos AS artistas
    LIMIT 1
    """
    with neo4j_driver.session() as session:
        record = session.run(query, uid=user_id).single()

    if record:
        generos.extend(record.get("generos") or [])
        artistas.extend(record.get("artistas") or [])

    return _limpiar_lista(generos), _limpiar_lista(artistas)


def _ids_zset(nombre: str, limite: int = 50) -> List[Tuple[str, float]]:
    return [(tid, float(score)) for tid, score in redis_client.zrevrange(nombre, 0, limite - 1, withscores=True)]


def _candidatos_por_preferencias(
    generos: List[str],
    artistas: List[str],
    excluidas: set,
    limite_por_grupo: int = 45,
) -> Dict[str, Dict[str, Any]]:
    candidatos: Dict[str, Dict[str, Any]] = {}

    def agregar(track_id: str, score: float, evidencia: str) -> None:
        if track_id in excluidas:
            return
        item = candidatos.setdefault(track_id, {"score": 0.0, "evidence": []})
        item["score"] += score
        if evidencia not in item["evidence"]:
            item["evidence"].append(evidencia)

    for artista in artistas:
        for tid, pop in _ids_zset(f"ranking:artista:{normalizar_clave(artista)}", limite_por_grupo):
            agregar(
                tid,
                1.20 + min(pop / 100.0, 1.0) * 0.20,
                f"va con {artista}, uno de los artistas que elegiste",
            )

    for genero in generos:
        for tid, pop in _ids_zset(f"ranking:genero:{normalizar_clave(genero)}", limite_por_grupo):
            agregar(
                tid,
                1.00 + min(pop / 100.0, 1.0) * 0.15,
                f"va con tu gusto por {genero}",
            )

    return candidatos


def _construir_vector_perfil(
    user_id: str,
    historial: List[Dict[str, Any]],
    generos: List[str],
    artistas: List[str],
    ultima_cancion_gustada_id: Optional[str] = None,
) -> Tuple[Optional[np.ndarray], str, Optional[str]]:
    """
    Crea el perfil musical del usuario con tres niveles:
    1. Likes reales del usuario.
    2. Última canción gustada, si se pasa desde compatibilidad anterior.
    3. Preferencias iniciales de géneros/artistas.
    """
    vectores: List[np.ndarray] = []
    ejemplo_like: Optional[str] = None

    for interaccion in historial:
        if interaccion["rating"] >= 4:
            vector = _vector_cancion(interaccion["track_id"])
            if vector is not None:
                vectores.append(vector)
                if ejemplo_like is None:
                    ejemplo_like = interaccion.get("titulo") or _titulo_track(interaccion["track_id"])
        if len(vectores) >= 25:
            break

    if vectores:
        return np.mean(vectores, axis=0).astype("float32"), "likes", ejemplo_like

    if ultima_cancion_gustada_id:
        vector = _vector_cancion(ultima_cancion_gustada_id)
        if vector is not None:
            return vector.astype("float32"), "ultima_cancion", _titulo_track(ultima_cancion_gustada_id)

    ids_preferencia: List[str] = []
    for item in _candidatos_por_preferencias(generos, artistas, set(), limite_por_grupo=20):
        ids_preferencia.append(item)
        if len(ids_preferencia) >= 35:
            break

    for tid in ids_preferencia:
        vector = _vector_cancion(tid)
        if vector is not None:
            vectores.append(vector)

    if vectores:
        ejemplo_preferencia = artistas[0] if artistas else (generos[0] if generos else None)
        return np.mean(vectores, axis=0).astype("float32"), "preferencias", ejemplo_preferencia

    return None, "", None


def _buscar_por_contenido(
    vector_perfil: Optional[np.ndarray],
    fuente_perfil: str,
    ejemplo_perfil: Optional[str],
    excluidas: set,
    limite: int = 80,
) -> Dict[str, Dict[str, Any]]:
    candidatos: Dict[str, Dict[str, Any]] = {}

    if vector_perfil is None:
        return candidatos
    if db_clients.faiss_index.ntotal == 0 or not db_clients.faiss_track_ids:
        return candidatos

    k = min(db_clients.faiss_index.ntotal, max(limite, len(excluidas) + 30))
    distancias, indices = db_clients.faiss_index.search(vector_perfil.reshape(1, -1).astype("float32"), k)

    if fuente_perfil in {"likes", "ultima_cancion"} and ejemplo_perfil:
        evidencia = f"como te gustó “{ejemplo_perfil}”, buscamos algo con una vibra parecida"
    elif fuente_perfil == "preferencias" and ejemplo_perfil:
        evidencia = f"encaja con lo que elegiste al empezar: {ejemplo_perfil}"
    else:
        evidencia = "encaja con lo que has ido marcando en tu perfil"

    for rank, (distancia, idx) in enumerate(zip(distancias[0], indices[0])):
        if idx < 0 or idx >= len(db_clients.faiss_track_ids):
            continue
        tid = db_clients.faiss_track_ids[idx]
        if tid in excluidas:
            continue

        similitud = 1.0 / (1.0 + max(float(distancia), 0.0))
        bono_rank = 1.0 - (rank / max(k, 1))
        score = (similitud * 0.85) + (bono_rank * 0.15)
        candidatos[tid] = {
            "score": score,
            "distance": float(distancia),
            "evidence": [evidencia],
        }

    return candidatos


def _buscar_colaborativo(user_id: str, limite: int = 60) -> Dict[str, Dict[str, Any]]:
    query = """
    MATCH (u:Usuario {id: $uid})-[ru:CALIFICO]->(base:Cancion)<-[rs:CALIFICO]-(otro:Usuario)-[rr:CALIFICO]->(rec:Cancion)
    WHERE ru.valor >= 4
      AND rs.valor >= 4
      AND rr.valor >= 4
      AND NOT (u)-[:CALIFICO]->(rec)
    RETURN rec.id AS track_id,
           count(DISTINCT base) AS coincidencias,
           count(DISTINCT otro) AS usuarios_similares,
           sum(rr.valor) AS suma_ratings,
           collect(DISTINCT coalesce(base.titulo, base.id)) AS canciones_base
    ORDER BY coincidencias DESC, usuarios_similares DESC, suma_ratings DESC
    LIMIT $limite
    """

    candidatos: Dict[str, Dict[str, Any]] = {}
    with neo4j_driver.session() as session:
        resultado = session.run(query, uid=user_id, limite=limite)
        for record in resultado:
            coincidencias = int(record["coincidencias"])
            usuarios = int(record["usuarios_similares"])
            suma = float(record["suma_ratings"])
            canciones_base = list(record.get("canciones_base") or [])
            ejemplo = canciones_base[0] if canciones_base else None
            raw_score = coincidencias * 2.0 + usuarios * 1.2 + suma / 5.0

            if ejemplo:
                evidencia = f"a personas que también disfrutaron “{ejemplo}” les gustaron canciones como esta"
            else:
                evidencia = "a personas con gustos parecidos también les gustó esta línea de canciones"

            candidatos[record["track_id"]] = {
                "score": raw_score,
                "coincidencias": coincidencias,
                "usuarios": usuarios,
                "evidence": [evidencia],
            }
    return candidatos


def _candidatos_populares(excluidas: set, limite: int = 100) -> Dict[str, Dict[str, Any]]:
    candidatos: Dict[str, Dict[str, Any]] = {}
    for tid, score in _ids_zset("ranking:popularidad", limite):
        if tid in excluidas:
            continue
        candidatos[tid] = {
            "score": score,
            "evidence": ["está sonando bastante dentro del catálogo"],
        }
    return candidatos


def _fusionar_candidatos(
    destino: Dict[str, Dict[str, Any]],
    nuevos: Dict[str, Dict[str, Any]],
    componente: str,
) -> None:
    for tid, info in nuevos.items():
        item = destino.setdefault(tid, {"raw": {}, "evidence": []})
        item["raw"][componente] = max(float(info.get("score", 0.0)), item["raw"].get(componente, 0.0))
        for evidencia in info.get("evidence", []):
            if evidencia not in item["evidence"]:
                item["evidence"].append(evidencia)


def _pesos_activos(historial: List[Dict[str, Any]], generos: List[str], artistas: List[str]) -> Dict[str, float]:
    likes = [h for h in historial if h["rating"] >= 4]
    tiene_preferencias = bool(generos or artistas)

    if not likes:
        return {
            "content": 0.25 if tiene_preferencias else 0.05,
            "collaborative": 0.00,
            "preference": 0.50 if tiene_preferencias else 0.15,
            "popularity": 0.25 if tiene_preferencias else 0.80,
        }

    return {
        "content": 0.40,
        "collaborative": 0.30,
        "preference": 0.15,
        "popularity": 0.15,
    }


def _normalizar_y_rankear(
    candidatos: Dict[str, Dict[str, Any]],
    pesos_base: Dict[str, float],
    limite: int = 5,
) -> List[Dict[str, Any]]:
    if not candidatos:
        return []

    maximos: Dict[str, float] = {}
    for componente in COMPONENT_LABELS:
        maximos[componente] = max((info["raw"].get(componente, 0.0) for info in candidatos.values()), default=0.0)

    componentes_disponibles = {
        componente
        for componente, maximo in maximos.items()
        if maximo > 0 and pesos_base.get(componente, 0.0) > 0
    }
    if not componentes_disponibles:
        return []

    total_pesos = sum(pesos_base[c] for c in componentes_disponibles)
    pesos = {c: pesos_base[c] / total_pesos for c in componentes_disponibles}

    rankeados: List[Dict[str, Any]] = []
    for tid, info in candidatos.items():
        metadata = _metadatos_uno(tid)
        if not metadata:
            continue

        contribuciones: Dict[str, float] = {}
        score_final = 0.0

        for componente in COMPONENT_LABELS:
            maximo = maximos.get(componente, 0.0)
            valor_raw = info["raw"].get(componente, 0.0)
            valor_norm = (valor_raw / maximo) if maximo > 0 else 0.0
            valor_norm = max(0.0, min(valor_norm, 1.0))
            if componente in pesos:
                contribucion = valor_norm * pesos[componente]
                contribuciones[componente] = contribucion
                score_final += contribucion

        if score_final <= 0:
            continue

        metadata["score"] = round(score_final, 4)
        metadata["components"] = {k: round(v, 4) for k, v in contribuciones.items() if v > 0}
        metadata["signals"] = info.get("evidence", [])[:4]
        metadata["reason"] = _explicar_recomendacion(metadata, contribuciones)
        rankeados.append(metadata)

    rankeados.sort(key=lambda item: item["score"], reverse=True)
    return _diversificar_por_artista(rankeados, limite)


def _explicar_recomendacion(metadata: Dict[str, Any], contribuciones: Dict[str, float]) -> str:
    if not contribuciones:
        return "La agregué porque puede ser una buena opción para seguir descubriendo música."

    componente_principal = max(contribuciones, key=contribuciones.get)
    senales = [str(s) for s in metadata.get("signals", []) if str(s).strip()]
    primera_senal = senales[0] if senales else ""

    if componente_principal == "collaborative":
        if primera_senal:
            return f"{_mayuscula_inicial(primera_senal)}. Por eso pensé que también podía encajarte."
        return "A personas con gustos parecidos a los tuyos también les gustó esta canción, así que la puse en tu lista."

    if componente_principal == "content":
        if primera_senal:
            return f"{_mayuscula_inicial(primera_senal)}. Por eso la agregué a tus recomendaciones."
        return "La agregué porque tiene una vibra parecida a lo que has marcado con me gusta."

    if componente_principal == "preference":
        if primera_senal:
            return f"La elegí porque {primera_senal}."
        return "La elegí porque se acerca a los géneros o artistas que seleccionaste."

    if primera_senal:
        return f"La puse como una opción segura porque {primera_senal}."
    return "La puse como una opción segura para seguir explorando canciones con buena recepción."


def _diversificar_por_artista(canciones: List[Dict[str, Any]], limite: int) -> List[Dict[str, Any]]:
    """Evita que el top final se llene de un solo artista."""
    seleccionadas: List[Dict[str, Any]] = []
    diferidas: List[Dict[str, Any]] = []
    contador_artistas: Counter[str] = Counter()

    for cancion in canciones:
        artista_principal = cancion.get("artista", "").split(";")[0]
        clave_artista = normalizar_clave(artista_principal)
        if contador_artistas[clave_artista] < 2:
            seleccionadas.append(cancion)
            contador_artistas[clave_artista] += 1
        else:
            diferidas.append(cancion)
        if len(seleccionadas) >= limite:
            break

    if len(seleccionadas) < limite:
        for cancion in diferidas:
            if cancion not in seleccionadas:
                seleccionadas.append(cancion)
            if len(seleccionadas) >= limite:
                break

    return seleccionadas[:limite]


def get_hybrid_recommendations(
    user_id: str,
    initial_genres: Optional[List[str]] = None,
    initial_artists: Optional[List[str]] = None,
    ultima_cancion_gustada_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Recomendador híbrido con interfaz humana:
    - Usuario nuevo: preferencias iniciales + canciones populares.
    - Usuario con historial: similitud musical + usuarios parecidos + ranking.
    - Caja blanca: razón breve y natural para cada canción.
    """
    generos, artistas = _preferencias_usuario(user_id, initial_genres, initial_artists)
    historial = _historial_usuario(user_id)
    excluidas = {inter["track_id"] for inter in historial}

    candidatos: Dict[str, Dict[str, Any]] = {}

    vector_perfil, fuente_perfil, ejemplo_perfil = _construir_vector_perfil(
        user_id=user_id,
        historial=historial,
        generos=generos,
        artistas=artistas,
        ultima_cancion_gustada_id=ultima_cancion_gustada_id,
    )

    _fusionar_candidatos(
        candidatos,
        _buscar_por_contenido(vector_perfil, fuente_perfil, ejemplo_perfil, excluidas),
        "content",
    )
    _fusionar_candidatos(candidatos, _buscar_colaborativo(user_id), "collaborative")
    _fusionar_candidatos(candidatos, _candidatos_por_preferencias(generos, artistas, excluidas), "preference")
    _fusionar_candidatos(candidatos, _candidatos_populares(excluidas), "popularity")

    return _normalizar_y_rankear(candidatos, _pesos_activos(historial, generos, artistas), limite=5)
