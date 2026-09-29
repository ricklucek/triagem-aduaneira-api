-- Tags operacionais dos usuários.
--
-- A coluna users.role continua sendo a fonte de autorização técnica. As tags
-- classificam o perfil para filtros, seletores e atribuições operacionais.

BEGIN;

CREATE TABLE IF NOT EXISTS user_tags (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    code VARCHAR(64) NOT NULL,
    name VARCHAR(80) NOT NULL,
    description TEXT,
    color VARCHAR(24) NOT NULL DEFAULT 'slate',
    is_master BOOLEAN NOT NULL DEFAULT FALSE,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id),
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    CONSTRAINT uq_user_tags_org_code UNIQUE (organization_id, code)
);

CREATE INDEX IF NOT EXISTS ix_user_tags_organization_id
    ON user_tags (organization_id);
CREATE INDEX IF NOT EXISTS ix_user_tags_active
    ON user_tags (active);
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_tags_master_per_org
    ON user_tags (organization_id)
    WHERE is_master;

CREATE TABLE IF NOT EXISTS user_tag_assignments (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    tag_id UUID NOT NULL REFERENCES user_tags(id),
    assigned_by_id UUID REFERENCES users(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_tag_assignments_user_tag UNIQUE (user_id, tag_id)
);

CREATE INDEX IF NOT EXISTS ix_user_tag_assignments_user_id
    ON user_tag_assignments (user_id);
CREATE INDEX IF NOT EXISTS ix_user_tag_assignments_tag_id
    ON user_tag_assignments (tag_id);
CREATE INDEX IF NOT EXISTS ix_user_tag_assignments_assigned_by_id
    ON user_tag_assignments (assigned_by_id);

INSERT INTO user_tags (
    id,
    organization_id,
    code,
    name,
    description,
    color,
    is_master,
    is_system,
    active,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    organizations.id,
    defaults.code,
    defaults.name,
    defaults.description,
    defaults.color,
    defaults.is_master,
    TRUE,
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM organizations
CROSS JOIN (
    VALUES
        ('admin', 'Admin', 'Acesso administrativo mestre da organização.', 'rose', TRUE),
        ('comercial', 'Comercial', 'Atuação comercial e responsabilidade por clientes.', 'emerald', FALSE),
        ('analista-da', 'Analista DA', 'Analista de despacho aduaneiro.', 'blue', FALSE),
        ('analista-ae', 'Analista AE', 'Analista de assessoria especial.', 'violet', FALSE),
        ('credenciamento', 'Credenciamento', 'Atuação em cadastros e credenciamentos.', 'amber', FALSE),
        ('operacao', 'Operação', 'Atuação operacional geral.', 'slate', FALSE)
) AS defaults(code, name, description, color, is_master)
ON CONFLICT (organization_id, code) DO NOTHING;

-- Converte o alias legado antes de vincular a tag mestre.
UPDATE users
SET role = 'admin'
WHERE role = 'administrador';

INSERT INTO user_tag_assignments (
    id,
    user_id,
    tag_id,
    assigned_by_id,
    created_at
)
SELECT
    gen_random_uuid(),
    users.id,
    user_tags.id,
    NULL,
    CURRENT_TIMESTAMP
FROM users
JOIN user_tags
  ON user_tags.organization_id = users.organization_id
 AND user_tags.code = CASE
        WHEN users.role = 'admin' THEN 'admin'
        WHEN users.role = 'comercial' THEN 'comercial'
        WHEN users.role = 'credenciamento' THEN 'credenciamento'
        ELSE 'operacao'
    END
ON CONFLICT (user_id, tag_id) DO NOTHING;

COMMIT;

-- Rollback manual:
-- DROP TABLE IF EXISTS user_tag_assignments;
-- DROP TABLE IF EXISTS user_tags;
