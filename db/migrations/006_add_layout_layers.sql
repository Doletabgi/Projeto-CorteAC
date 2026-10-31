-- Migração 006: Suporte a persistência de camadas (layers) por layout
-- Compatível com MySQL 8.0 Central

ALTER TABLE layouts ADD COLUMN IF NOT EXISTS layers INT NULL DEFAULT NULL;
