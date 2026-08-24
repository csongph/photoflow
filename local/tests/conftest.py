from __future__ import annotations

import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parents[1] / "data" / "test_photoflow.db"
TEST_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["LOCAL_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["EVENT_ROOT_DIR"] = str(Path(__file__).resolve().parents[1] / "test_events")
