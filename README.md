# CRM Unificado EPEM — Midnight Command Center

> **Versión**: 0.1.0 MVP — 03/06/2026  
> **Deadline**: 10 de junio 2026  
> **Estado**: ✅ OPERATIVO

---

## 🚀 Quick Start

```bash
# 1. PostgreSQL (nativo, puerto 5432)
# Ya está corriendo como servicio postgresql-x64-18

# 2. Backend
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Frontend
cd frontend
npm run dev

# 4. Abrir
# http://localhost:3000
# admin@epem.com / admin123
```

---

## 🏗️ Stack

| Componente | Tecnología | Puerto |
|-----------|-----------|:------:|
| Frontend | Next.js 15 + Linear Refero Dark Theme | 3000 |
| Backend | FastAPI (Python 3.12) | 8000 |
| Base de datos | PostgreSQL 18 (nativo Windows) | 5432 |
| ETL Scheduler | APScheduler (sync cada 1h) | background |
| Fuente de datos | EPEM MySQL slave (192.168.0.241) | 3306 |

---

## 📊 Dashboard (MVP)

### Vista Home
- 4 KPIs: Leads nuevos, Gestionados, Ventas, Conversión
- Trend △% vs período anterior
- Filtros: fecha, unidad de negocio, fuente, contrato (activo/finalizado/todos)

### Vista Vendedores
- Ranking de 50 vendedores
- Columnas sortables: leads, gestionados, ventas, conversión, cartera
- Filtro de contrato intercambiable

---

## 🔌 API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/auth/login` | Login JWT |
| GET | `/api/auth/me` | Usuario actual |
| GET | `/api/dashboard/home` | KPIs principales |
| GET | `/api/dashboard/vendedores` | Ranking de vendedores |
| GET | `/api/health` | Health check |
| POST | `/api/etl/sync` | Sync incremental |
| POST | `/api/etl/sync/full` | Sync completo |

---

## 🗄️ Base de Datos

- **Schema**: `crm`
- **Tablas**: `leads_unificados` (735K), `lead_tracking`, `users`, `sync_log`
- **Fuente**: `sales_opportunities` de EPEM MySQL
- **Sync**: cada 60 min, configurable vía `SYNC_INTERVAL_MINUTES` en `.env`

---

## 🔐 Roles

| Rol | Permisos |
|-----|----------|
| Admin | Todo — todas las UN |
| Supervisor | Solo su UN (`enterprise_id`) |
| Vendedor | Solo sus leads (`seller_id`) |

---

## 📁 Estructura

```
crm-unificado/
├── .env                        # Variables de entorno
├── docker-compose.yml          # (alternativa Docker — no usado en prod)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── venv/                   # Python virtualenv
│   ├── app/
│   │   ├── main.py             # FastAPI app
│   │   ├── core/
│   │   │   ├── config.py       # Settings desde .env
│   │   │   └── database.py     # Conexión asyncpg
│   │   ├── routers/
│   │   │   ├── auth.py         # JWT login
│   │   │   ├── dashboard.py    # KPIs + vendedores
│   │   │   ├── health.py       # Health check
│   │   │   └── etl_routes.py   # Sync triggers
│   │   └── models/             # SQLAlchemy models (futuro)
│   ├── etl/
│   │   ├── __main__.py         # CLI entry point
│   │   ├── sync.py             # Sync engine
│   │   └── scheduler.py        # APScheduler
│   └── db/
│       └── init.sql            # Schema inicial
├── frontend/
│   ├── public/
│   │   └── logo-epem.png
│   └── app/
│       ├── layout.tsx          # Root layout
│       ├── page.tsx            # Login page
│       ├── globals.css         # Linear dark theme
│       └── dashboard/
│           ├── layout.tsx      # Sidebar + nav
│           ├── page.tsx        # Home KPIs
│           └── vendedores/
│               └── page.tsx    # Ranking
└── logs/
```

---

## 🐛 Bugs Fixeados (9 en total)

1. Puertos Docker en conflicto → PostgreSQL nativo
2. Credenciales EPEM incorrectas en `.env`
3. Columnas INT overflow → VARCHAR
4. JSONB serialization en `execute_values`
5. `normalized_phone` VARCHAR(20) → VARCHAR(100)
6. Docker hostname 'postgres' → localhost
7. bcrypt 3.2.2 incompatible con passlib → 4.0.1
8. Password hash corrupto por escape de `$` en PowerShell
9. `seller_id IS NOT NULL` en cláusula suelta del SQL → movido a WHERE

---

## ⏭️ Próximos pasos (Fase 2)

- [ ] ThinkChat ETL
- [ ] Vista Funnel de conversión
- [ ] Vista Supervisores
- [ ] Alertas (leads >24h, campañas vencidas)
- [ ] Top campañas por ROI
- [ ] API Botmaker outbound (key pendiente de Desarrollo)
- [ ] Mapeo de líneas WhatsApp
- [ ] Tracking de salud de cartera de clientes/leads?
