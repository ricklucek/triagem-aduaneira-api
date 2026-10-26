def can_manage_scope_lifecycle(user) -> bool:
    """Single policy for deactivation, reactivation and inactive-scope access."""
    return getattr(user, "role", None) == "admin"
