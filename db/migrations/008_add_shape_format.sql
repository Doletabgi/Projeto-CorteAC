-- Migração 008: Formato e multiplicador do molde (1x1, 4x1, 6x1)
-- Compatível com MySQL 8.0 Central

ALTER TABLE shapes ADD COLUMN IF NOT EXISTS shape_format VARCHAR(8) NOT NULL DEFAULT '1x1';
