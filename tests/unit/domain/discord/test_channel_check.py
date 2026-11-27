from wgm.domain.discord.channel_check import (
    NEEDED,
    ChannelCheck,
    channel_permissions,
)

GUILD = "1"
VIEW, SEND, EMBED, HISTORY = (NEEDED[n] for n in NEEDED)
ALL = VIEW | SEND | EMBED | HISTORY


def _perms(
    everyone: int = ALL,
    member_roles: dict[str, int] | None = None,
    overwrites: list[tuple[str, int, int]] | None = None,
) -> int:
    member_roles = member_roles or {}
    roles = [{"id": GUILD, "permissions": str(everyone)}] + [
        {"id": rid, "permissions": str(p)} for rid, p in member_roles.items()
    ]
    return channel_permissions(
        guild_id=GUILD,
        member_id="app",
        member_role_ids=list(member_roles),
        roles=roles,
        overwrites=[
            {"id": oid, "allow": str(a), "deny": str(d)}
            for oid, a, d in overwrites or []
        ],
    )


def test_server_permissions_apply_without_overwrites() -> None:
    assert _perms() & ALL == ALL


def test_everyone_overwrite_can_hide_a_channel() -> None:
    assert not _perms(overwrites=[(GUILD, 0, VIEW)]) & VIEW


def test_role_overwrite_beats_everyone_overwrite() -> None:
    perms = _perms(member_roles={"r": 0}, overwrites=[(GUILD, 0, VIEW), ("r", VIEW, 0)])

    assert perms & VIEW


def test_member_overwrite_is_applied_last() -> None:
    perms = _perms(overwrites=[("app", 0, SEND)])

    assert not perms & SEND


def test_administrators_have_everything() -> None:
    assert _perms(everyone=0, member_roles={"admin": 1 << 3}) == -1


def test_report_lists_missing_permissions_and_how_to_fix() -> None:
    check = ChannelCheck("9", {"View Channel": True, "Send Messages": False})

    assert not check.ok
    assert check.report() == (
        "Permissions the app needs in <#9>:\n"
        "✅ View Channel\n"
        "❌ Send Messages\n"
        "To fix: open the channel → **Edit Channel** → **Permissions** → "
        "add this app → allow the ones marked ❌."
    )


def test_report_has_no_fix_when_everything_is_there() -> None:
    check = ChannelCheck("9", {"View Channel": True})

    assert check.ok
    assert "To fix" not in check.report()
