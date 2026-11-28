"""Events and the members signed up for them."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import DateTimeUTC
from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _values(enum: type[StrEnum]) -> list[str]:
    """Store enum values (attending), not names (ATTENDING)."""
    return [member.value for member in enum]


class SignupStatus(StrEnum):
    """Whether a member is coming."""

    ATTENDING = "attending"
    TENTATIVE = "tentative"
    """Might come, or coming late."""
    NOT_ATTENDING = "not_attending"
    """Can't make it; tracked so managers know who answered."""


class Event(UUIDAuditBase):
    """A PvX event in one Discord server."""

    __tablename__ = "event"

    guild_id: Mapped[str] = mapped_column(String(32), index=True)
    """Discord server the event belongs to."""
    title: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(32))
    """Siege, Boonstone, Riftstone, Archboss, Guild Raid, Arena or Other."""
    starts_at: Mapped[datetime] = mapped_column(DateTimeUTC(timezone=True))
    created_by: Mapped[str] = mapped_column(String(32))
    """Discord user ID of the manager who created it."""
    channel_id: Mapped[str | None] = mapped_column(String(32), default=None)
    message_id: Mapped[str | None] = mapped_column(String(32), default=None)
    """The event's post in Discord, updated as people sign up."""
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTimeUTC(timezone=True), default=None
    )
    """When members can no longer change their answer (admins still can)."""
    closed_post_at: Mapped[datetime | None] = mapped_column(
        DateTimeUTC(timezone=True), default=None
    )
    """When the post was locked after closing; empty until the job does it."""
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTimeUTC(timezone=True), default=None
    )
    """When an admin cancelled it. The post stays up, marked Cancelled."""
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTimeUTC(timezone=True), default=None
    )
    """When an admin deleted it. Its post is removed and the event is hidden,
    but the row and its sign ups are kept."""
    deleted_by: Mapped[str | None] = mapped_column(String(32), default=None)
    """Discord user ID of the admin who deleted it."""

    signups: Mapped[list["Signup"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Signup.created_at",
    )


class Signup(UUIDAuditBase):
    """One member's answer for an event: attending, tentative or not attending."""

    __tablename__ = "signup"
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)

    event_id: Mapped[UUID] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(32))
    """Discord user ID."""
    character_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[SignupStatus] = mapped_column(
        Enum(SignupStatus, native_enum=False, length=16, values_callable=_values)
    )
    role: Mapped[str | None] = mapped_column(String(16), default=None)
    """Tank, Healer or DPS. Empty for members who are not attending."""
    class_name: Mapped[str | None] = mapped_column(String(32), default=None)
    """The class they're bringing, such as Crusader, once they confirm it."""
    reason: Mapped[str | None] = mapped_column(String(200), default=None)
    """Why they can't come, if they said. Only admins see it."""
    changed_by: Mapped[str | None] = mapped_column(String(32), default=None)
    """Discord user ID of whoever set this answer: the member or an admin."""
    late: Mapped[bool] = mapped_column(default=False, server_default="0")
    """Set by an admin after sign-ups closed; shown as (late) on the post."""

    event: Mapped[Event] = relationship(back_populates="signups")


class SignupAction(StrEnum):
    """What happened to a member's answer."""

    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"


class SignupChange(UUIDAuditBase):
    """One change to the roster, kept as history. `created_at` is when."""

    __tablename__ = "signup_change"

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(32))
    """The member whose answer changed."""
    character_name: Mapped[str] = mapped_column(String(64))
    action: Mapped[SignupAction] = mapped_column(
        Enum(SignupAction, native_enum=False, length=16, values_callable=_values)
    )
    status: Mapped[SignupStatus | None] = mapped_column(
        Enum(SignupStatus, native_enum=False, length=16, values_callable=_values),
        default=None,
    )
    """The new answer; empty when removed."""
    role: Mapped[str | None] = mapped_column(String(16), default=None)
    changed_by: Mapped[str] = mapped_column(String(32))
    """Discord user ID of the member or admin who made the change."""
    late: Mapped[bool] = mapped_column(default=False)
    """Made after sign-ups closed."""


class MemberClass(UUIDAuditBase):
    """The class a member last confirmed for a role, offered first next time."""

    __tablename__ = "member_class"
    __table_args__ = (UniqueConstraint("guild_id", "user_id", "role"),)

    guild_id: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16))
    class_name: Mapped[str] = mapped_column(String(32))
