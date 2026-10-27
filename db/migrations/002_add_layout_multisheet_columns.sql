-- Migração 002: Suporte a Múltiplos Layouts por Sessão (Nesting Multi-Placa)
-- Compatível com MySQL 8.0 Central

ALTER TABLE layouts ADD COLUMN IF NOT EXISTS layout_index INT NOT NULL DEFAULT 0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_left DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_right DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_top DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS margin_bottom DOUBLE DEFAULT 10.0;
ALTER TABLE layouts ADD COLUMN IF NOT EXISTS placed_pieces_json LONGTEXT NULL;

CREATE INDEX IF NOT EXISTS idx_layouts_session_index ON layouts (session_id, layout_index);
