from wgm.domain.discord.permissions import is_server_manager, may_run

ROLE_IDS = {"wgm-admin": "900", "Officer": "901"}


def test_everyone_may_run_unrestricted_commands() -> None:
    assert may_run((), [], "0", {})


def test_members_with_an_allowed_role_may_run() -> None:
    assert may_run(("wgm-admin",), ["123", "900"], "0", ROLE_IDS)


def test_members_without_it_may_not() -> None:
    assert not may_run(("wgm-admin",), ["901"], "0", ROLE_IDS)


def test_missing_roles_never_match() -> None:
    assert not may_run(("wgm-admin",), ["901"], "0", {})


def test_server_managers_may_always_run() -> None:
    assert may_run(("wgm-admin",), [], str(1 << 5), {})
    assert is_server_manager(str((1 << 5) | (1 << 3)))
    assert not is_server_manager("")
