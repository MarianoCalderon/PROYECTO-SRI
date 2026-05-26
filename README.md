# Descubrir: Recomendador Musical Híbrido

Proyecto final para la asignatura de Sistemas de Recomendación / Búsqueda y Recuperación de Información.

Integrantes:
- Calderón Núñez Mariano Marcel
- Chacón Ambrosio David Efraín
- Ramírez Couoh Cristhian Leonel

<img src="/Imagenes/Mariano.jpeg" height="200"> <img src="/Imagenes/David.jpeg" height="200"> <img src="/Imagenes/Cristhian.jpeg" height="200">

---

## ¿Qué hace?

**Descubrir** recomienda canciones a partir de preferencias iniciales, actividad del usuario, canciones populares, similitud musical y relaciones entre usuarios.

La interfaz conserva el estilo del prototipo original: onboarding sencillo, tarjetas limpias, botón de me gusta, botón de omitir y explicaciones naturales para cada recomendación.

Por dentro, el sistema conserva una arquitectura híbrida:

- **Redis:** metadatos de canciones y rankings.
- **Neo4j:** usuarios, canciones y relaciones `CALIFICO`.
- **FAISS:** búsqueda por similitud musical usando audio-features.
- **FastAPI:** servicios web REST.
- **Frontend HTML/CSS/JS:** interfaz de usuario con Web Worker.

---

## Cómo cumple la rúbrica

| Requisito | Implementación |
|---|---|
| Inicio en frío | El usuario selecciona géneros y artistas. Si aún no tiene historial, el sistema recomienda usando esas preferencias y canciones populares. |
| Modelo híbrido | Combina similitud musical, usuarios parecidos, preferencias iniciales y popularidad. |
| Ranking y Boosting | Redis mantiene el ranking global y rankings por género/artista. Los likes suben la popularidad y las omisiones ayudan a evitar repetir canciones. |
| Recomendación orgánica y caja blanca | Cada canción incluye una explicación humana de por qué aparece, sin mostrar fórmulas ni porcentajes al usuario. |
| Usabilidad | Onboarding, tarjetas limpias, botones de me gusta/omitir, mensajes de carga y diseño responsivo. |
| Extras | Web Worker, FAISS persistente, Neo4j como grafo, Redis para ranking y ETL con Pandas/NumPy. |

---

## Historial inicial en Neo4j

El proyecto carga un historial base pequeño:

- `Usuario_Frecuente_1`
- `Usuario_Frecuente_2`
- 2 canciones semilla
- 3 relaciones `CALIFICO`

Esto evita que Neo4j arranque completamente vacío, pero tampoco llena el grafo con muchos usuarios artificiales. La idea es que el sistema empiece con recomendaciones por inicio en frío y que el componente colaborativo gane fuerza conforme los usuarios reales dan likes u omiten canciones.

---

## Requisitos

- Python 3.10 o superior. En Windows se recomienda Python 3.12 si ya está instalado.
- Docker Desktop o Docker Engine con Docker Compose.
- El archivo `spotify_data.csv` incluido en la raíz del proyecto.

---

## Cómo correrlo en local

### 1. Entrar al proyecto

```bash
cd PROYECTO-SRI-main
```

### 2. Crear entorno virtual e instalar dependencias

Windows:

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Levantar Redis y Neo4j

```bash
docker compose up -d
```

Servicios:

- Redis: `localhost:6379`
- Neo4j Browser: `http://localhost:7474`
- Neo4j Bolt: `bolt://localhost:7687`
- Usuario Neo4j: `neo4j`
- Contraseña Neo4j: `password123`

### 4. Cargar datos reales

```bash
python seed_real_data.py
```

Este paso:

1. Lee `spotify_data.csv`.
2. Carga 15,000 canciones reproducibles.
3. Guarda metadatos y rankings en Redis.
4. Crea rankings por género y artista para el onboarding.
5. Construye y persiste el índice FAISS en `data/`.
6. Crea un historial base pequeño en Neo4j, similar al prototipo original.

### 5. Iniciar la API

```bash
python -m uvicorn main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Estado del sistema para la presentación:

```text
http://127.0.0.1:8000/status/
```

### 6. Abrir el frontend

En otra terminal:

```bash
cd frontend
python -m http.server 5500
```

Abrir:

```text
http://localhost:5500
```

---

## Flujo sugerido 

1. Abrir `/status/` para mostrar que Redis, FAISS y Neo4j están activos.
2. Abrir el frontend.
3. Crear un usuario nuevo, por ejemplo `DavidC`.
4. Seleccionar géneros y artistas favoritos.
5. Explicar que las primeras recomendaciones usan inicio en frío.
6. Dar me gusta a varias canciones.
7. Crear otro usuario, por ejemplo `Mariano`, y repetir algunas preferencias.
8. Abrir Neo4j Browser y mostrar usuarios, canciones y relaciones `CALIFICO`.
9. Explicar que el colaborativo aparece cuando varios usuarios comparten gustos.

---

## Consultas útiles en Neo4j

Ver todos los usuarios:

```cypher
MATCH (u:Usuario)
RETURN u.id AS usuario, u.generos_favoritos AS generos, u.artistas_favoritos AS artistas
ORDER BY usuario;
```

Ver las interacciones de un usuario:

```cypher
MATCH (u:Usuario {id:'DavidC'})-[r:CALIFICO]->(c:Cancion)
RETURN u.id AS usuario, c.titulo AS cancion, c.artista AS artista, c.genero AS genero, r.valor AS valor
ORDER BY r.timestamp DESC;
```

Ver el grafo de relaciones:

```cypher
MATCH p=(u:Usuario)-[r:CALIFICO]->(c:Cancion)
RETURN p
LIMIT 80;
```

Ver usuarios con canciones en común:

```cypher
MATCH (u:Usuario {id:'DavidC'})-[r1:CALIFICO]->(c:Cancion)<-[r2:CALIFICO]-(otro:Usuario)
WHERE r1.valor >= 4 AND r2.valor >= 4 AND otro.id <> u.id
RETURN otro.id AS usuario_parecido, count(c) AS canciones_en_comun, collect(c.titulo)[0..5] AS canciones_compartidas
ORDER BY canciones_en_comun DESC;
```
