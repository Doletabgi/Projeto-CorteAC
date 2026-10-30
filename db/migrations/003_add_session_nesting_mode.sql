-- Migração 003: Suporte a 4 Camadas de UX e Seleção de Modo de Encaixe
-- Compatível com MySQL 8.0 Central

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS nesting_mode VARCHAR(50) DEFAULT 'auto';
