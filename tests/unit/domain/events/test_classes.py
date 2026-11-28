from wgm.domain.events.classes import CLASSES, MAX_OPTIONS, WEAPONS, ranked, the_rest


def test_the_list_matches_questlog() -> None:
    assert {role: len(group) for role, group in CLASSES.items()} == {
        "Tank": 12,
        "Healer": 8,
        "DPS": 25,
    }
    assert WEAPONS["Seeker"] == "Longbow + Wand"


def test_unplayed_classes_keep_the_list_order() -> None:
    assert ranked("Tank", {})[:3] == ["Berserker", "Crusader", "Disciple"]


def test_popular_classes_come_first_and_off_role_ones_join() -> None:
    names = ranked("Healer", {"Oracle": 5, "Seeker": 9, "Crusader": 1})

    assert names[:3] == ["Seeker", "Oracle", "Crusader"]
    assert len(names) == 9


def test_the_dropdown_never_has_more_than_25() -> None:
    names = ranked("DPS", {"Seeker": 3})

    assert len(names) == MAX_OPTIONS
    assert names[0] == "Seeker"
    assert "Spellblade" not in names


def test_the_rest_groups_what_was_left_out_by_role() -> None:
    rest = the_rest(ranked("DPS", {"Seeker": 3}))

    assert list(rest) == ["Tank", "Healer", "DPS"]
    assert "Seeker" not in rest["Healer"]
    assert rest["DPS"] == ["Spellblade"]
