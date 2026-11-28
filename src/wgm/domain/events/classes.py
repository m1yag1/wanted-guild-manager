"""Throne and Liberty classes (weapon pairs), grouped by the role they usually play.

From questlog.gg. Update this list when a patch adds or renames classes.
"""

CLASSES: dict[str, tuple[tuple[str, str], ...]] = {
    "Tank": (
        ("Berserker", "Sword + Daggers"),
        ("Crusader", "Greatsword + Sword"),
        ("Disciple", "Sword + Staff"),
        ("Guardian", "Orb + Sword"),
        ("Juggernaut", "Gauntlet + Sword"),
        ("Justicar", "Orb + Greatsword"),
        ("Mauler", "Gauntlet + Greatsword"),
        ("Raider", "Crossbow + Sword"),
        ("Soulcrusher", "Gauntlet + Orb"),
        ("Steelheart", "Spear + Sword"),
        ("Templar", "Sword + Wand"),
        ("Warden", "Sword + Longbow"),
    ),
    "Healer": (
        ("Darkblighter", "Daggers + Wand"),
        ("Fury", "Crossbow + Wand"),
        ("Invocator", "Staff + Wand"),
        ("Oracle", "Orb + Wand"),
        ("Paladin", "Greatsword + Wand"),
        ("Seeker", "Longbow + Wand"),
        ("Tormentor", "Gauntlet + Wand"),
        ("Voidlance", "Spear + Wand"),
    ),
    "DPS": (
        ("Archon", "Gauntlet + Staff"),
        ("Battleweaver", "Crossbow + Staff"),
        ("Cavalier", "Spear + Crossbow"),
        ("Crucifix", "Orb + Crossbow"),
        ("Destroyer", "Gauntlet + Spear"),
        ("Enigma", "Orb + Staff"),
        ("Eradicator", "Spear + Staff"),
        ("Gladiator", "Spear + Greatsword"),
        ("Impaler", "Spear + Longbow"),
        ("Infiltrator", "Longbow + Daggers"),
        ("Liberator", "Longbow + Staff"),
        ("Lunarch", "Orb + Daggers"),
        ("Mobilist", "Gauntlet + Longbow"),
        ("Outrider", "Crossbow + Greatsword"),
        ("Polaris", "Orb + Spear"),
        ("Predator", "Gauntlet + Daggers"),
        ("Ranger", "Longbow + Greatsword"),
        ("Ravager", "Greatsword + Daggers"),
        ("Scorpion", "Crossbow + Daggers"),
        ("Scout", "Longbow + Crossbow"),
        ("Scryer", "Orb + Longbow"),
        ("Sentinel", "Staff + Greatsword"),
        ("Shadowdancer", "Spear + Daggers"),
        ("Shrike", "Gauntlet + Crossbow"),
        ("Spellblade", "Staff + Daggers"),
    ),
}
WEAPONS = {name: weapons for group in CLASSES.values() for name, weapons in group}
"""Every class's weapon pair, by class name."""
MAX_OPTIONS = 25
"""Discord shows at most 25 options in one dropdown."""


def ranked(role: str, counts: dict[str, int]) -> list[str]:
    """Classes for a role's dropdown: most picked by the guild first.

    Off-role classes the guild has played in this role join the list. Ties
    keep the list's order, with the role's own classes first.
    """
    own = [name for name, _ in CLASSES[role]]
    others = [name for name in WEAPONS if name not in own and counts.get(name)]
    candidates = own + others
    order = {name: index for index, name in enumerate(candidates)}
    return sorted(candidates, key=lambda name: (-counts.get(name, 0), order[name]))[
        :MAX_OPTIONS
    ]


def the_rest(shown: list[str]) -> dict[str, list[str]]:
    """Classes not in `shown`, grouped by role, for the "Other classes" step."""
    return {
        role: rest
        for role, group in CLASSES.items()
        if (rest := [name for name, _ in group if name not in shown])
    }
