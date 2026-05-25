import redis
from neo4j import GraphDatabase
import faiss

# Cliente Redis para almacenamiento en caché y rankings veloces
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Driver de Neo4j para el manejo de relaciones complejas del grafo
neo4j_driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))

# Índice FAISS para búsqueda ágil de vecinos más cercanos (5 dimensiones de audio)
d = 5 
faiss_index = faiss.IndexFlatL2(d)