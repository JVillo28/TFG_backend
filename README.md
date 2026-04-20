# BioSim — Backend

API REST en FastAPI que da soporte al Trabajo de Fin de Grado **"Simulación microbiótica para el ahorro de costes en la investigación"** (Escola Superior de Enxeñaría Informática, Universidade de Vigo).

El backend gestiona el JSON Schema que define la estructura de las configuraciones de simulación, las investigaciones (*research*) creadas por los investigadores, y el endpoint conversacional que delega en un proveedor LLM (Groq Cloud por defecto, Ollama en modo offline).

**Frontend asociado:** [../frontend/](../frontend) — Angular 21 + Angular Material + TypeScript.

---

## 1 · Requisitos

| Componente | Versión mínima |
|---|---|
| Python | 3.11 (recomendado 3.12) |
| MySQL | 8.0 |
| [uv](https://docs.astral.sh/uv/) | última estable |
| Clave de [Groq Cloud](https://console.groq.com/keys) *o* instalación local de [Ollama](https://ollama.com/) | — |

`uv` se instala con:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux / macOS
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## 2 · Instalación

### 2.1 Base de datos

Crea una base de datos MySQL vacía y un usuario con permisos sobre ella:

```sql
CREATE DATABASE biosim CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'biosim'@'localhost' IDENTIFIED BY 'contraseña_segura';
GRANT ALL PRIVILEGES ON biosim.* TO 'biosim'@'localhost';
FLUSH PRIVILEGES;
```

### 2.2 Dependencias y variables de entorno

Desde la raíz del repositorio:

```bash
uv sync                          # crea .venv/ e instala dependencias
cp .env.example .env             # rellenar con credenciales reales
```

Edita `.env` con los valores que correspondan a tu entorno — al mínimo, `DATABASE_URL` y `LLM_API_KEY` (si usas Groq).

### 2.3 LLM local (opcional)

Si prefieres ejecutar el modelo en local sin depender de servicios externos:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b-instruct
ollama serve                      # arranca el runtime en :11434
```

Después, descomenta el bloque **Opción B** en `.env` y comenta el bloque **Opción A**.

---

## 3 · Ejecución

Arranca el servidor de desarrollo con *hot-reload*:

```bash
uv run uvicorn main:app --reload --port 8000
```

En el primer arranque, la aplicación crea automáticamente las tablas necesarias (`users`, `admin`, `research`) a partir de los modelos SQLAlchemy. No hay que ejecutar migraciones manualmente.

Puntos de entrada:

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
├── tests/                # pytest + SQLite en memoria
├── config.py             # Settings (Pydantic Settings)
├── main.py               # Entrypoint: app = create_app()
├── pyproject.toml        # Dependencias y metadatos
└── uv.lock               # Lockfile reproducible
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

Cobertura actual: **68 tests** (unitarios + integración) en estado *passing*, incluyendo el endpoint conversacional con cliente LLM mockeado.

---

## 7 · Calidad del código

```bash
uv run ruff check .                # lint
uv run ruff check --fix .          # lint con autofix
uv run ruff format .               # formateo
```

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
