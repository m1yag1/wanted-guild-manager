"""Run command line tools through invoke's runner.

Tasks pass their invoke `Context` in, so commands run the same way as any other
`c.run(...)`. Wrapping it adds two things the tasks need: an argument list
instead of a shell string (quoted safely), and a `CommandError` that keeps the
exit code and stderr for a clear message.
"""

import functools
import io
import shlex
from collections.abc import Mapping, Sequence

from attrs import field, frozen
from invoke.context import Context


class CommandError(RuntimeError):
    """A command exited with an error."""

    def __init__(self, args: Sequence[str], returncode: int, stderr: str) -> None:
        super().__init__(f"{args[0]} exited with {returncode}: {stderr.strip()}")
        self.args_ = list(args)
        self.returncode = returncode
        self.stderr = stderr


@frozen
class Shell:
    """Runs commands with an invoke `Context`, plus optional environment variables."""

    context: Context
    env: Mapping[str, str] = field(factory=dict)

    def run(
        self, args: Sequence[str], *, stdin: str | None = None, capture: bool = True
    ) -> str:
        """Run a command and return its output.

        Args:
            args: The command and its arguments.
            stdin: Text to send to the command's standard input.
            capture: Return the output instead of showing it as it runs.

        Returns:
            Standard output when captured, otherwise an empty string.

        Raises:
            CommandError: The command exited with a non-zero status.
        """
        # warn=True: report failures as CommandError instead of invoke's own.
        result = self.context.run(
            shlex.join(args),
            hide=capture,
            warn=True,
            env=dict(self.env),
            in_stream=False if stdin is None else io.StringIO(stdin),
        )
        if not result.ok:
            raise CommandError(args, result.exited, result.stderr)
        return result.stdout if capture else ""


# Print immediately, so messages appear in order with the output of the
# commands that run after them.
say = functools.partial(print, flush=True)
