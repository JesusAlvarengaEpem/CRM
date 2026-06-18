-- CRM Unificado EPEM — Database Initialization
-- Stage 0 — Infraestructura Base

-- Schema
CREATE SCHEMA IF NOT EXISTS crm;

-- Tabla central: leads unificados
CREATE TABLE IF NOT EXISTS crm.leads_unificados (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_phone VARCHAR(20),
    fullname VARCHAR(500),
    email VARCHAR(255),
    enterprise_id INT,
    branch_id INT,
    sources JSONB DEFAULT '[]'::jsonb,        -- ["botmaker", "thinkchat"]
    
    -- Botmaker fields
    bm_customer_id VARCHAR(100),
    botmaker_observation TEXT,
    botmaker_chat_platform VARCHAR(50),
    ad_id VARCHAR(100),
    campaign_id INT,
    whatsapp_number VARCHAR(50),
    
    -- CRM fields
    seller_id INT,
    closer_id INT,
    contract_id INT,
    status INT,
    creator INT,
    observation TEXT,
    lead VARCHAR(255),
    
    -- Classification
    classification_flags JSONB DEFAULT '{}'::jsonb,
    
    -- Tracking
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_updated_at TIMESTAMP DEFAULT NOW(),
    
    -- EPEM reference
    epem_opportunity_id INT NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_leads_phone ON crm.leads_unificados(normalized_phone);
CREATE INDEX IF NOT EXISTS idx_leads_enterprise ON crm.leads_unificados(enterprise_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON crm.leads_unificados(status);
CREATE INDEX IF NOT EXISTS idx_leads_seller ON crm.leads_unificados(seller_id);
CREATE INDEX IF NOT EXISTS idx_leads_first_seen ON crm.leads_unificados(first_seen_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_epem_id ON crm.leads_unificados(epem_opportunity_id);

-- Tabla de tracking (historial de estados)
CREATE TABLE IF NOT EXISTS crm.lead_tracking (
    id SERIAL PRIMARY KEY,
    lead_id UUID REFERENCES crm.leads_unificados(id) ON DELETE CASCADE,
    from_status INT,
    to_status INT,
    seller_id INT,
    timestamp TIMESTAMP,
    source VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_tracking_lead ON crm.lead_tracking(lead_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tracking_source ON crm.lead_tracking(source) WHERE source IS NOT NULL;

-- Usuarios
CREATE TABLE IF NOT EXISTS crm.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    fullname VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'vendedor',  -- admin, supervisor, vendedor
    enterprise_id INT,
    seller_id INT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON crm.users(email);

-- Log de sync
CREATE TABLE IF NOT EXISTS crm.sync_log (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,          -- 'botmaker', 'manual'
    records_upserted INT DEFAULT 0,
    records_skipped INT DEFAULT 0,
    errors TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
