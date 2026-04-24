"""Entry point for ``python -m glossary``."""

import sys

from .cli import main

sys.exit(main())
