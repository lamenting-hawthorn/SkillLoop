"""Support ``python -m skillloop`` as a stable CLI entry point."""

from skillloop.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
