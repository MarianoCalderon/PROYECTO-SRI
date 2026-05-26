# Consultas útiles para Neo4j Browser

Abrir Neo4j Browser:

```text
http://localhost:7474
```

Credenciales:

```text
usuario: neo4j
contraseña: password123
```

## Ver todos los usuarios

```cypher
MATCH (u:Usuario)
RETURN 
  u.id AS usuario,
  u.generos_favoritos AS generos,
  u.artistas_favoritos AS artistas
ORDER BY usuario;
```

## Ver cuántas interacciones tiene cada usuario

```cypher
MATCH (u:Usuario)
OPTIONAL MATCH (u)-[r:CALIFICO]->(:Cancion)
RETURN 
  u.id AS usuario,
  count(r) AS total_interacciones,
  sum(CASE WHEN r.valor >= 4 THEN 1 ELSE 0 END) AS likes,
  sum(CASE WHEN r.valor <= 2 THEN 1 ELSE 0 END) AS omitidas
ORDER BY total_interacciones DESC, usuario;
```

## Ver el grafo general

```cypher
MATCH p=(u:Usuario)-[r:CALIFICO]->(c:Cancion)
RETURN p
LIMIT 80;
```

## Ver un usuario específico

```cypher
MATCH p=(u:Usuario {id:'DavidC'})-[r:CALIFICO]->(c:Cancion)
RETURN p
ORDER BY r.timestamp DESC;
```

## Ver interacciones de un usuario en tabla

```cypher
MATCH (u:Usuario {id:'DavidC'})-[r:CALIFICO]->(c:Cancion)
RETURN 
  u.id AS usuario,
  c.titulo AS cancion,
  c.artista AS artista,
  c.genero AS genero,
  r.valor AS valor
ORDER BY r.timestamp DESC;
```

## Ver usuarios parecidos por canciones en común

```cypher
MATCH (u:Usuario {id:'DavidC'})-[r1:CALIFICO]->(c:Cancion)<-[r2:CALIFICO]-(otro:Usuario)
WHERE r1.valor >= 4
  AND r2.valor >= 4
  AND otro.id <> u.id
RETURN 
  otro.id AS usuario_parecido,
  count(c) AS canciones_en_comun,
  collect(c.titulo)[0..5] AS canciones_compartidas
ORDER BY canciones_en_comun DESC;
```

## Ver candidatos colaborativos

```cypher
MATCH (u:Usuario {id:'DavidC'})-[r1:CALIFICO]->(base:Cancion)<-[r2:CALIFICO]-(otro:Usuario)-[r3:CALIFICO]->(rec:Cancion)
WHERE r1.valor >= 4
  AND r2.valor >= 4
  AND r3.valor >= 4
  AND otro.id <> u.id
  AND NOT (u)-[:CALIFICO]->(rec)
RETURN 
  rec.titulo AS recomendacion,
  rec.artista AS artista,
  rec.genero AS genero,
  count(DISTINCT otro) AS usuarios_parecidos
ORDER BY usuarios_parecidos DESC
LIMIT 10;
```
