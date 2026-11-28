from wgm.domain.discord.schemas import FormField, InteractionData, Resolved


def test_form_fields_are_found_by_id() -> None:
    data = InteractionData(
        components=[
            FormField(type=1, components=[FormField(type=4, custom_id="a", value="x")])
        ]
    )

    assert (data.field("a"), data.field("b")) == ("x", "")


def test_picked_users_without_details_show_their_id() -> None:
    assert Resolved().name("4242") == "4242"
