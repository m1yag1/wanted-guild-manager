from wgm.domain.discord.commands import WGM_COMMAND, help_text, run_command
from wgm.domain.discord.schemas import InteractionData, InteractionOption


def test_wgm_has_a_help_subcommand() -> None:
    assert WGM_COMMAND["name"] == "wgm"
    assert [option["name"] for option in WGM_COMMAND["options"]] == ["help"]


def test_help_lists_every_subcommand() -> None:
    assert "`/wgm help`: Show the commands you can use" in help_text()


def test_a_bare_command_gets_the_help_text() -> None:
    reply = run_command(InteractionData(name="wgm"))

    assert reply.data is not None
    assert reply.data.content.startswith("Unknown command.")


def test_other_commands_get_the_help_text() -> None:
    data = InteractionData(name="other", options=[InteractionOption("help", 1)])

    reply = run_command(data)

    assert reply.data is not None
    assert reply.data.content.startswith("Unknown command.")
