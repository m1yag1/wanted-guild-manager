"""Turn expected task failures into a one-line message instead of a traceback."""

import functools
from collections.abc import Callable
from pathlib import Path

from invoke.exceptions import Exit

from tasks.shell import CommandError

# Failures a person can act on; anything else is a bug and keeps its traceback.
EXPECTED = (CommandError, FileNotFoundError, ValueError, RuntimeError)


def friendly_errors[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Report expected failures as `Error: ...` and exit with status 1."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except CommandError as error:
            detail = error.stderr.strip() or "see the output above"
            command = Path(error.args_[0]).name
            raise Exit(
                f"Error: {command} failed ({detail}).", code=error.returncode
            ) from None
        except EXPECTED as error:
            raise Exit(f"Error: {error}", code=1) from None

    return wrapper
