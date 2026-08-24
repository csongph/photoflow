from __future__ import annotations

from .config import ensure_directories
from .database import init_db


def main() -> None:
    ensure_directories()
    init_db()
    print("MomentLink local database initialized.")


if __name__ == "__main__":
    main()
