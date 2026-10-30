-- Migração 004: Índice Composto para Performance do Catálogo de Moldes (Grid View Matrix)
-- Compatível com SQLite 3 e MySQL 8.0

CREATE INDEX IF NOT EXISTS idx_shapes_article_size_name 
ON shapes(article_id, size, name);
