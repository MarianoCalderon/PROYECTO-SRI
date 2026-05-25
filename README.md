# Proyecto-BRIW
Repositorio para las entregas del proyecto de la asignatura Búsqueda y Recuperación de Información en la Web.

Integrantes:
- Calderón Núñez Mariano Marcel 
- Chacón Ambrosio David Efraín 
- Ramírez Couoh Cristhian Leonel

 <img src="/Media/Mariano.jpeg" height="200"> <img src="/Media/Andrea.jpeg" height="200"> <img src="/Media/Mauro.jpeg" height="200"> <img src="/Media/Carlos.jpeg" height="200">
# Descubrir: Motor de Recomendación Musical Híbrido

Un sistema de recomendación musical Full-Stack construido con **FastAPI**, **Neo4j**, **Redis** y **FAISS**. Este proyecto resuelve los desafíos clásicos de los sistemas de recomendación utilizando persistencia políglota y procesamiento asíncrono para entregar una experiencia de usuario fluida y transparente.

---

## Características Principales

Este motor fue diseñado cumpliendo con rigurosos estándares de ingeniería de software e implementa las siguientes soluciones algorítmicas:

* **Mitigación del Inicio en Frío:** Sistema de *onboarding* dinámico que perfila al usuario nuevo basándose en sus géneros y artistas favoritos, extrayendo opciones en tiempo real desde una muestra de 15,000 canciones del catálogo.
* **Modelo Híbrido por Intercalado:** Combina Filtrado Colaborativo (basado en grafos) y Filtrado por Contenido (basado en vectores) para equilibrar la precisión y la novedad.
* **Ranking y Boosting en Tiempo Real:** Utiliza estructuras de datos en RAM para calcular la popularidad global al instante y empujar tendencias (*boosting*) sin el efecto burbuja.
* **Explicabilidad (Caja Blanca):** Cada recomendación le explica al usuario exactamente por qué fue sugerida (ej. *"Recomendado porque a usuarios con tus mismos gustos también les gustó"*).
* **Usabilidad Avanzada:** Interfaz minimalista (Glassmorphism claro) que utiliza peticiones asíncronas (`fetch`) y procesamiento en segundo plano (`Web Workers`) para que la pantalla nunca se congele.

---

## Arquitectura y Tecnologías

El proyecto sigue una arquitectura orientada a microservicios con separación estricta de responsabilidades:

### Backend & Datos
* **FastAPI (Python):** Controlador principal y exposición de endpoints REST.
* **Neo4j (Grafo):** Almacena la matriz de interacciones Usuario-Ítem y resuelve el Filtrado Colaborativo sin usar costosos `JOINs` de SQL.
* **Redis (Clave-Valor):** Caché en memoria para almacenar metadatos de las canciones y resolver el motor de popularidad (ZSET) en milisegundos.
* **FAISS (Búsqueda Vectorial):** Motor de inteligencia artificial de Meta para la búsqueda de similitud matemática (k-NN) basada en características acústicas (*danceability, energy, tempo*, etc.).
* **Pandas & NumPy:** Pipeline ETL para la ingesta y limpieza del dataset original de Spotify.

### Frontend
* **HTML5 / CSS3:** Diseño responsivo inspirado en el ecosistema Apple, separando la lógica visual de la estructura.
* **Vanilla JavaScript:** Consumo de APIs y manipulación del DOM.
* **Web Workers:** Delegación del renderizado de componentes para liberar el hilo principal del navegador.

---

## Requisitos Previos

Asegúrate de tener instalados en tu máquina local:
* [Python 3.9+](https://www.python.org/downloads/)
* [Docker y Docker Compose](https://www.docker.com/products/docker-desktop)
* Dataset original de Spotify (`spotify_data.csv`) ubicado en la raíz del proyecto.

---

## Instalación y Configuración

Sigue estos pasos para levantar el entorno completo en tu máquina local.

**1. Clonar el repositorio**
```bash
git clone [https://github.com/MarianoCalderon/PROYECTO-SRI.git](https://github.com/MarianoCalderon/PROYECTO-SRI.git)
cd PROYECTO-SRI
```
**2. Crear el entorno virtual e instalar dependencias**
```bash
python -m venv venv
venv\Scripts\activate  # En Windows
pip install -r requirements.txt
```
**3. Levantar las bases de datos (Docker)**
* Inicia los contenedores de Redis y Neo4j en segundo plano.
```bash
docker-compose up -d
```
(Nota: Neo4j puede tardar unos 40 segundos en estar listo para aceptar conexiones).

**4. Poblar el clúster con datos reales**
* Ejecuta el pipeline de datos. Esto extraerá una muestra aleatoria de 15,000 canciones, indexará los vectores en FAISS, guardará el ranking en Redis y creará el grafo base en Neo4j.

```bash
python seed_real_data.py
```
**5. Iniciar la API (Backend)**
```bash
uvicorn main:app --reload
```
La API estará disponible en: http://127.0.0.1:8000
**6. Abrir la Interfaz de Usuario**
*Abre una nueva terminal, navega a la carpeta frontend e inicia un servidor ligero:
```bash
cd frontend
python -m http.server 5500
```
Visita http://localhost:5500 en tu navegador.

### Mantenimiento
Si necesitas reiniciar la base de datos por completo (por ejemplo, para cargar un volumen distinto de datos), ejecuta:
```bash
docker-compose down -v
docker-compose up -d
python seed_real_data.py
```



