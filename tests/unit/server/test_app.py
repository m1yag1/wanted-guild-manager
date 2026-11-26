from wgm.lib.settings import Settings
from wgm.server.app import create_app


def test_uses_the_settings_it_is_given(settings: Settings) -> None:
    assert create_app(settings).state.settings is settings
