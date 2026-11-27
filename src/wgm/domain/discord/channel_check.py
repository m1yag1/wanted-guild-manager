"""Check that the app can post event messages in a channel, and say how to fix it.

Discord's rule for a member's permissions in a channel: start from the server's
@everyone role plus the member's roles, then apply the channel's overwrites for
@everyone, then for the member's roles, then for the member.
See https://discord.com/developers/docs/topics/permissions
"""

from typing import Any

from attrs import frozen

from wgm.domain.discord.client import DiscordApiError, DiscordClient

ADMINISTRATOR = 1 << 3
NEEDED = {
    "View Channel": 1 << 10,
    "Send Messages": 1 << 11,
    "Embed Links": 1 << 14,
    "Read Message History": 1 << 16,
}


def channel_permissions(
    *,
    guild_id: str,
    member_id: str,
    member_role_ids: list[str],
    roles: list[dict[str, Any]],
    overwrites: list[dict[str, Any]],
) -> int:
    """A member's permission bits in a channel."""
    role_perms = {role["id"]: int(role["permissions"]) for role in roles}
    allowed = role_perms.get(guild_id, 0)
    for role_id in member_role_ids:
        allowed |= role_perms.get(role_id, 0)
    if allowed & ADMINISTRATOR:
        return -1  # every permission
    by_id = {o["id"]: (int(o["allow"]), int(o["deny"])) for o in overwrites}
    allow, deny = by_id.get(guild_id, (0, 0))
    allowed = (allowed & ~deny) | allow
    role_allow = role_deny = 0
    for role_id in member_role_ids:
        allow, deny = by_id.get(role_id, (0, 0))
        role_allow |= allow
        role_deny |= deny
    allowed = (allowed & ~role_deny) | role_allow
    allow, deny = by_id.get(member_id, (0, 0))
    return (allowed & ~deny) | allow


@frozen
class ChannelCheck:
    """Which of the needed permissions the app has in a channel."""

    channel_id: str
    present: dict[str, bool]

    @property
    def ok(self) -> bool:
        """The app can post event messages there."""
        return all(self.present.values())

    def report(self) -> str:
        """A checklist, plus how to fix it when something is missing."""
        lines = [
            f"{'✅' if has else '❌'} {name}" for name, has in self.present.items()
        ]
        text = f"Permissions the app needs in <#{self.channel_id}>:\n" + "\n".join(
            lines
        )
        if self.ok:
            return text
        return (
            f"{text}\nTo fix: open the channel → **Edit Channel** → **Permissions** → "
            "add this app → allow the ones marked ❌."
        )


async def check_channel(
    discord: DiscordClient, *, guild_id: str, app_id: str, channel_id: str
) -> ChannelCheck:
    """Work out the app's permissions in a channel. Unseen channels fail all four."""
    try:
        channel = await discord.channel(channel_id)
        roles = await discord.roles(guild_id)
        member = await discord.member(guild_id, app_id)
    except DiscordApiError:
        return ChannelCheck(channel_id, dict.fromkeys(NEEDED, False))
    perms = channel_permissions(
        guild_id=guild_id,
        member_id=app_id,
        member_role_ids=list(member.get("roles", [])),
        roles=roles,
        overwrites=list(channel.get("permission_overwrites", [])),
    )
    return ChannelCheck(
        channel_id, {name: bool(perms & bit) for name, bit in NEEDED.items()}
    )
