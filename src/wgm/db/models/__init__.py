"""ORM models. Import every model here so Alembic sees all tables."""

from wgm.db.models.event import Event, Signup, SignupStatus

__all__ = ["Event", "Signup", "SignupStatus"]
