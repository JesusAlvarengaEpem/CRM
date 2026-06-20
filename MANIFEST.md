# MANIFEST - crm-unificado.

*Generado por Minerva - 2026-06-20 00:04:06*

```markdown
# MANIFEST.md – CRM Unificado

## Propósito
Backend unificado para la gestión de clientes (CRM), que integra datos desde múltiples fuentes mediante procesos ETL, expone una API REST y persiste en base de datos relacional.

## Estructura del proyecto
```
crm-unificado/
├── backend/
│   ├── app/
│   │   ├── core/          # Configuración, seguridad, dependencias
│   │   ├── middleware/     # Autenticación, logging, CORS
│   │   ├── models/        # Modelos de datos (SQLAlchemy / ORM)
│   │   ├── routers/       # Endpoints de la API (clientes, contactos, etc.)
│   │   └── services/      # Lógica de negocio y comunicación con DB
│   ├── db/
│   │   └── migrations/    # Migraciones de esquema (Alembic)
│   └── etl/               # Scripts de extracción, transformación y carga
├── docker-compose.yml     # Orquestación de servicios (app + DB)
├── .env                   # Variables de entorno (credenciales, URLs)
├── .dockerignore
├── .gitignore
├── README.md
└── MANIFEST.md
```

## Archivos clave
- **`backend/app/core/config.py`** – Carga variables desde `.env` y centraliza ajustes.
- **`backend/app/routers/`** – Define rutas como `/clientes`, `/contactos`, `/oportunidades`.
- **`backend/app/services/`** – Contiene la lógica transaccional y validaciones.
- **`backend/db/migrations/`** – Control de versiones del esquema; ejecutar con Alembic.
- **`backend/etl/`** – Scripts para importar/exportar datos desde/hacia sistemas externos.
- **`docker-compose.yml`** – Levanta la aplicación y la base de datos (PostgreSQL/MySQL) en contenedores.

## Cómo usar

### 1. Requisitos previos
- Docker y Docker Compose instalados.
- Python 3.10+ (para desarrollo local sin contenedores).

### 2. Configuración
Copiar `.env.example` (si existe) a `.env` y ajustar:
- `DATABASE_URL` (cadena de conexión)
- `SECRET_KEY` (para JWT)
- Credenciales de fuentes ETL

### 3. Ejecución con Docker
```bash
docker-compose up -d
```
Esto inicia la API (normalmente en `http://localhost:8000`) y la base de datos.

### 4. Migraciones
```bash
docker-compose exec backend alembic upgrade head
```
O localmente: `cd backend && alembic upgrade head`

### 5. Procesos ETL
Ejecutar scripts dentro del contenedor o localmente:
```bash
docker-compose exec backend python etl/importar_clientes.py
```

### 6. Documentación de la API
Acceder a Swagger UI en `/docs` o ReDoc en `/redoc` (si se usa FastAPI).

## Notas adicionales
- El middleware de autenticación protege los endpoints sensibles; se requiere token JWT en el header `Authorization: Bearer <token>`.
- Los modelos de datos están en `backend/app/models/`; cualquier cambio debe ir acompañado de una nueva migración.
- Los scripts ETL pueden programarse con cron o ejecutarse manualmente para sincronizar datos.

---
*Última actualización: según el estado del repositorio.*
```