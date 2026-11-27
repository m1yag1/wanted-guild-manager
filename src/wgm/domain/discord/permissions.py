"""Who may run which /wgm command.

Each command lists the role names allowed to run it; an empty list means
everyone. Members with Discord's Manage Server permission may always run
admin commands, so a server owner can get started before any WGM role exists.
"""

ADMIN_ROLE = "wgm-admin"
WGM_ROLES = (ADMIN_ROLE,)
"""Roles `/wgm setup` creates."""

MANAGE_GUILD = 1 << 5


def is_server_manager(permissions: str) -> bool:
    """Whether a member's permission bits include Manage Server."""
    return bool(int(permissions or "0") & MANAGE_GUILD)


def may_run(
    allowed_roles: tuple[str, ...],
    member_role_ids: list[str],
    member_permissions: str,
    role_ids_by_name: dict[str, str],
) -> bool:
    """Whether a member may run a command limited to `allowed_roles`."""
    if not allowed_roles or is_server_manager(member_permissions):
        return True
    allowed_ids = {role_ids_by_name.get(name) for name in allowed_roles}
    return any(role_id in allowed_ids for role_id in member_role_ids)
