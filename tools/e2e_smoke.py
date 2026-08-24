from __future__ import annotations

import json
import time
from pathlib import Path

import httpx


def main() -> int:
    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=10)
    event = client.post("/api/events", json={"name": "E2E Smoke", "preset_id": "event_natural"}).json()
    client.post(f"/api/events/{event['id']}/start").raise_for_status()
    client.post(f"/api/events/{event['id']}/simulate-photo").raise_for_status()

    photos = []
    deadline = time.time() + 25
    root = Path(event["root_path"])
    while time.time() < deadline:
        photos = client.get(f"/api/events/{event['id']}/photos").json()
        if (
            list((root / "ORIGINAL").glob("*.jpg"))
            and list((root / "FINISHED").glob("*.jpg"))
            and list((root / "PREVIEWS").glob("*.jpg"))
            and list((root / "THUMBNAILS").glob("*.jpg"))
        ):
            break
        time.sleep(1)

    result = {
        "event_id": event["id"],
        "originals": len(list((root / "ORIGINAL").glob("*.jpg"))),
        "finished": len(list((root / "FINISHED").glob("*.jpg"))),
        "previews": len(list((root / "PREVIEWS").glob("*.jpg"))),
        "thumbnails": len(list((root / "THUMBNAILS").glob("*.jpg"))),
        "photo_status": photos[0]["status"] if photos else None,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["originals"] and result["finished"] and result["previews"] and result["thumbnails"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
