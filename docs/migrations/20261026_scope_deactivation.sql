-- Aplicar ANTES de publicar a API de inativação de escopos.
-- Não altera o status nem os dados dos registros existentes. Pode ser reaplicada.
BEGIN;
ALTER TABLE scopes ADD COLUMN IF NOT EXISTS archived_from_status VARCHAR(16);
ALTER TABLE scopes ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE scopes ADD COLUMN IF NOT EXISTS archived_by_id UUID REFERENCES users(id) ON DELETE SET NULL;
COMMIT;
