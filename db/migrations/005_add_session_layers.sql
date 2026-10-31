-- Migração 005: Suporte a persistência de camadas (layers) na sessão
-- Compatível com MySQL 8.0 Central

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS layers INT NULL DEFAULT NULL;
