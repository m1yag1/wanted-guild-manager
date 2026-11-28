"""Shark facts for event posts that have no description. 🦈"""

import random

SHARK_FACTS = (
    "Sharks have been around for over 400 million years, longer than trees.",
    "A shark's skeleton is cartilage, not bone.",
    "Some sharks lose and regrow thousands of teeth in a lifetime.",
    "The whale shark is the biggest fish in the sea.",
    "Shark skin is covered in tiny tooth-like scales called denticles.",
    "Sharks can sense the faint electric fields of their prey.",
    "A hammerhead's wide head helps it scan the sea floor for prey.",
    "Greenland sharks can live for centuries.",
    "The shortfin mako is one of the fastest sharks in the ocean.",
    "Cookiecutter sharks bite neat round plugs out of much bigger animals.",
)


def shark_fact(pick: random.Random | None = None) -> str:
    """A random shark fact."""
    return (pick or random.Random()).choice(SHARK_FACTS)  # noqa: S311  (not secret)
