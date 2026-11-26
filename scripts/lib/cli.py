"""Shared plumbing for the entry points in scripts/.

Every command in scripts/ is a thin argparse wrapper: it puts scripts/lib on
sys.path, parses arguments, calls library code and finishes with `cli.run`.
Operational logic belongs in the library modules, not in the entry point.
"""

import subprocess
import sys

# Expected failures: invalid input, missing files, failed or slow child commands.
OPERATIONAL_ERRORS = (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired)


def run(main, label, *, errors=OPERATIONAL_ERRORS):
    """Exit with main()'s status; report an expected failure as `LABEL: message`.

    Only the exception's message is printed, never a traceback or child output,
    so private values cannot leak. Anything outside `errors` propagates.
    """
    try:
        sys.exit(main())
    except errors as error:
        print(f'{label}: {error}', file=sys.stderr)
        sys.exit(1)
