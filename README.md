# TFG — Backend

API REST en FastAPI que da soporte al Trabajo de Fin de Grado **"Simulación microbiótica para el ahorro de costes en la investigación"** (Escola Superior de Enxeñaría Informática, Universidade de Vigo).

El backend gestiona el JSON Schema que define la estructura de las configuraciones de simulación, las investigaciones (*research*) creadas por los investigadores, y el endpoint conversacional que delega en un proveedor LLM (Groq Cloud por defecto, Ollama en modo offline).

**Frontend asociado:** [TFG_frontend](https://github.com/JVillo28/TFG_frontend) — Angular 21 + Angular Material + TypeScript.

---

## 1 · Despliegue rápido con Docker  · *recomendado*

La forma más sencilla de probar el sistema completo: un único `docker compose up` levanta backend + frontend + MySQL con la base de datos ya inicializada.

### 1.1 Requisitos

- [Docker](https://docs.docker.com/get-docker/) 24+ y **Docker Compose v2** (incluido en Docker Desktop).
- Una clave API de [Groq Cloud](https://console.groq.com/keys) — gratuita, sin tarjeta.

### 1.2 Pasos

```bash
# Clonar ambos repositorios LADO A LADO en una misma carpeta
git clone https://github.com/JVillo28/TFG_backend.git
git clone https://github.com/JVillo28/TFG_frontend.git

# Configurar variables (rellena al menos LLM_API_KEY)
cd TFG_backend
cp .env.docker.example .env.docker
$EDITOR .env.docker

# Arrancar
docker compose --env-file .env.docker up --build
```

Cuando el log muestre que los tres servicios están listos, abre [http://localhost:4200](http://localhost:4200). La base de datos arranca con el JSON Schema de simulación biológica precargado, listo para crear investigaciones.

### 1.3 Modo offline (Ollama local)

Por defecto se usa Groq Cloud por velocidad y sencillez. Para ejecutar el LLM localmente:

```bash
# 1. Edita .env.docker — comenta el bloque Groq y descomenta el de Ollama
# 2. Arranca con el profile offline:
docker compose --env-file .env.docker --profile offline up --build

# 3. La primera vez, descarga el modelo (~5 GB):
docker exec biosim-ollama ollama pull qwen2.5:7b-instruct
```

### 1.4 Comandos útiles

| Comando | Para qué |
|---|---|
| `docker compose --env-file .env.docker logs -f backend` | Ver logs del backend en tiempo real |
| `docker compose --env-file .env.docker exec mysql mysql -uroot -p` | Abrir un shell de MySQL dentro del contenedor |
| `docker compose --env-file .env.docker down` | Parar los servicios (mantiene los datos) |
| `docker compose --env-file .env.docker down -v` | Parar y borrar todos los datos para empezar limpio |

---

## 2 · Instalación manual (alternativa para desarrollo)

Si prefieres trabajar sin Docker —por ejemplo para depurar con tu IDE—, este es el flujo tradicional.

### 2.1 Requisitos

| Componente | Versión mínima |
|---|---|
| Python | 3.11 (recomendado 3.12) |
| MySQL | 8.0 |
| [uv](https://docs.astral.sh/uv/) | última estable |

`uv` se instala con:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux / macOS
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2.2 Base de datos

Carga la base de datos a partir del script versionado, que crea las tres tablas y precarga el JSON Schema:

```bash
mysql -u root -p < db/init.sql
```

Si prefieres un usuario dedicado (recomendado para uso prolongado):

```sql
CREATE USER 'biosim'@'localhost' IDENTIFIED BY 'contraseña_segura';
GRANT ALL PRIVILEGES ON biosim.* TO 'biosim'@'localhost';
FLUSH PRIVILEGES;
```

### 2.3 Dependencias y variables de entorno

```bash
uv sync                    # crea .venv/ e instala dependencias
cp .env.example .env       # editar con credenciales reales
```

En `.env` ajusta como mínimo `DATABASE_URL` y `LLM_API_KEY`.

### 2.4 Ejecución

```bash
uv run uvicorn main:app --reload --port 8000
```

El backend queda escuchando en `http://localhost:8000`.

### 2.5 LLM local (opcional)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b-instruct
ollama serve              # arranca el runtime en :11434
```

Después, edita `.env` para apuntar `LLM_BASE_URL` a `http://localhost:11434/v1`.

---

## 3 · Puntos de entrada

- **API:** [http://localhost:8000](http://localhost:8000)
- **Health check:** [GET /api/health](http://localhost:8000/api/health)
- **Documentación interactiva (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Esquema OpenAPI:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 4 · Contrato de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET`  | `/api/health` | Estado del servicio y de la base de datos |
| `GET`  | `/api/admin/schema` | Obtener el JSON Schema vigente |
| `PUT`  | `/api/admin/schema` | Actualizar el JSON Schema (valida Draft 2020-12) |
| `POST` | `/api/research` | Crear una investigación nueva |
| `GET`  | `/api/research/{id}` | Obtener una investigación por id |
| `GET`  | `/api/research/user/{userId}` | Listar investigaciones de un usuario |
| `PUT`  | `/api/research/{id}` | Actualizar una investigación |
| `POST` | `/api/chat/message` | Un turno del asistente conversacional |
| `GET`  | `/api/users/{userId}` | Obtener datos de usuario |

---

## 5 · Estructura del proyecto

```
backend/
├── app/
│   ├── api/              # Routers FastAPI (un archivo por dominio)
│   ├── models/           # Modelos SQLAlchemy (users, admin, research)
│   ├── schemas/          # DTOs Pydantic (request/response)
│   ├── services/         # Lógica de negocio y cliente LLM
│   ├── database.py       # Engine, SessionLocal, init_db
│   └── __init__.py       # create_app() — factory FastAPI
├── db/
│   └── init.sql          # Esquema relacional + JSON Schema precargado
├── tests/                # pytest + SQLite en memoria
├── config.py             # Settings (Pydantic Settings)
├── main.py               # Entrypoint: app = create_app()
├── pyproject.toml        # Dependencias y metadatos
├── Dockerfile            # Imagen de producción del backend
└── docker-compose.yml    # Orquestación local (mysql + backend + frontend)
```

Patrón de capas: **Route → Schema (validación) → Service (lógica) → Model (DB)**.

---

## 6 · Pruebas

El conjunto de pruebas usa *pytest* con SQLite en memoria para aislamiento total.

```bash
uv run pytest                      # toda la suite
uv run pytest -v                   # verbose
uv run pytest tests/test_chat.py   # archivo concreto
```

Cobertura actual: **79 tests** (unitarios + integración) en estado *passing*, incluyendo el endpoint conversacional con cliente LLM mockeado.

---

## 7 · Calidad del código

```bash
uv run ruff check .                # lint
uv run ruff check --fix .          # lint con autofix
uv run ruff format .               # formateo
```

El lint también se ejecuta en cada *push* mediante GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)).

---

## 8 · Stack tecnológico

- **FastAPI** 0.115 · framework web async
- **SQLAlchemy** 2.0 · ORM
- **Pydantic** v2 + Pydantic Settings · validación y config
- **PyMySQL** · driver MySQL
- **OpenAI Python SDK** · cliente LLM (compatible con Groq y Ollama)
- **jsonschema** · validación Draft 2020-12
- **pytest** · framework de pruebas
- **uv** · gestor de dependencias y entornos virtuales

---

## 9 · Licencia y autoría

Trabajo de Fin de Grado de **Jaime Villota Martínez**, curso 2025/2026.
Tutora: Analia María García · Cotutor: Guillermo Blanco.
Escola Superior de Enxeñaría Informática, Universidade de Vigo.
