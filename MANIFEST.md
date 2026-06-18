# MANIFEST - crm-unificado.

*Generado por Minerva - 2026-06-17 20:28:01*

```markdown
# MANIFEST.md - CRM Unificado

## Propósito
Sistema backend para un CRM unificado que centraliza datos de clientes, interacciones y procesos ETL. Proporciona una API RESTful para integración con frontends y servicios externos.

## Estructura del proyecto
```
.
├── backend/
│   ├── app/
│   │   ├── core/          # Configuración, seguridad, dependencias
│   │   ├── middleware/     # Autenticación, logging, CORS
│   │   ├── models/        # Modelos de datos (ORM)
│   │   ├── routers/       # Endpoints de la API
│   │   └── services/      # Lógica de negocio y casos de uso
│   ├── db/
│   │   └── migrations/    # Migraciones de base de datos (Alembic)
│   └── etl/               # Scripts de extracción, transformación y carga
├── .dockerignore
├── .env                   # Variables de entorno (no versionado)
├── docker-compose.yml     # Orquestación de servicios (API, DB, etc.)
└── README.md
```

## Archivos clave
- **`docker-compose.yml`**: Levanta la aplicación, base de datos y servicios auxiliares.
- **`.env`**: Define credenciales, URLs de base de datos y configuraciones sensibles.
- **`backend/app/core/`**: Contiene `config.py` y `security.py` para manejo de variables de entorno y autenticación.
- **`backend/app/routers/`**: Define los endpoints REST (clientes, usuarios, reportes, etc.).
- **`backend/app/models/`**: Modelos SQLAlchemy que representan las tablas de la base de datos.
- **`backend/db/migrations/`**: Migraciones versionadas con Alembic para evolución del esquema.
- **`backend/etl/`**: Scripts para importar/exportar datos desde fuentes externas (CSV, APIs, etc.).

## Cómo usar
1. **Configurar entorno**  
   Copia `.env.example` (si existe) a `.env` y ajusta las variables (DB, secretos, etc.).

2. **Iniciar servicios**  
   ```bash
   docker-compose up -d
   ```
   Esto levanta la API y la base de datos.

3. **Aplicar migraciones**  
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

4. **Ejecutar procesos ETL (opcional)**  
   ```bash
   docker-compose exec backend python etl/importar_clientes.py
   ```

5. **Acceder a la API**  
   La documentación interactiva estará disponible en `http://localhost:8000/docs` (si usa FastAPI).

## Notas adicionales
- El middleware incluye capa de autenticación (JWT) y registro de peticiones.
- Los servicios encapsulan la lógica de negocio, separada de los routers.
- La carpeta `etl` puede contener scripts independientes o tareas programadas con Celery/APScheduler.
```