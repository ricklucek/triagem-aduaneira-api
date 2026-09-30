-- Histórico imutável de operações e alterações reversíveis.
-- Aplicar antes de publicar a versão da API que expõe /audit/events.

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    actor_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    actor_name VARCHAR(255) NOT NULL,
    actor_email VARCHAR(255),
    module VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id UUID,
    operation_id UUID,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    reverses_event_id UUID NULL REFERENCES audit_events(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_event_changes (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES audit_events(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    entity_type VARCHAR(32) NOT NULL,
    entity_id UUID NOT NULL,
    scope_id UUID NULL REFERENCES scopes(id) ON DELETE SET NULL,
    subject_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    client_id UUID NULL REFERENCES clients(id) ON DELETE SET NULL,
    before_state JSONB,
    after_state JSONB,
    changed_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_audit_events_organization_id ON audit_events (organization_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_actor_user_id ON audit_events (actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_module ON audit_events (module);
CREATE INDEX IF NOT EXISTS ix_audit_events_action ON audit_events (action);
CREATE INDEX IF NOT EXISTS ix_audit_events_entity_type ON audit_events (entity_type);
CREATE INDEX IF NOT EXISTS ix_audit_events_entity_id ON audit_events (entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_operation_id ON audit_events (operation_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_reverses_event_id ON audit_events (reverses_event_id);
CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_events_org_created ON audit_events (organization_id, created_at);
CREATE INDEX IF NOT EXISTS ix_audit_events_org_operation ON audit_events (organization_id, operation_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_event_id ON audit_event_changes (event_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_organization_id ON audit_event_changes (organization_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_entity_type ON audit_event_changes (entity_type);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_entity_id ON audit_event_changes (entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_scope_id ON audit_event_changes (scope_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_subject_user_id ON audit_event_changes (subject_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_client_id ON audit_event_changes (client_id);
CREATE INDEX IF NOT EXISTS ix_audit_event_changes_event_entity ON audit_event_changes (event_id, entity_id);

-- Rollback manual (remove definitivamente todo o histórico):
-- DROP TABLE IF EXISTS audit_event_changes;
-- DROP TABLE IF EXISTS audit_events;
