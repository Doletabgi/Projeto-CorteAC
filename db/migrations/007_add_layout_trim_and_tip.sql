-- Migration 007: Adiciona suporte a persistencia de linha de refile CAM e zona de ponta (enfesto em degrau)
-- Aplicavel em SQLite e MySQL

ALTER TABLE layouts ADD COLUMN trim_cut_line_json TEXT NULL;
ALTER TABLE layouts ADD COLUMN tip_zone_json TEXT NULL;
ALTER TABLE layouts ADD COLUMN layers_tip INT NULL DEFAULT NULL;
