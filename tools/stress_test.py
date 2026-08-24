from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw


def make_image(path: Path, idx: int) -> None:
    img = Image.new("RGB", (1200, 800), ((idx * 17) % 255, (idx * 31) % 255, (idx * 47) % 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), f"PhotoFlow stress {idx}", fill=(255, 255, 255))
    img.save(path, "JPEG", quality=92)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100, choices=[50, 100, 500, 2000])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=20)
    event = client.post("/api/events", json={"name": f"Stress {args.count}", "preset_id": "event_natural"}).json()
    client.post(f"/api/events/{event['id']}/start").raise_for_status()
    incoming = Path(event["incoming_path"])

    start = time.time()
    for idx in range(args.count):
        make_image(incoming / f"STRESS_{idx:05d}.jpg", idx)

    deadline = time.time() + max(120, args.count * 4)
    while time.time() < deadline:
        photos = client.get(f"/api/events/{event['id']}/photos").json()
        dashboard = client.get("/api/dashboard").json()
        if dashboard["counts"].get("captured", 0) >= args.count and dashboard["counts"].get("queue", 0) == 0:
            break
        time.sleep(2)

    dashboard = client.get("/api/dashboard").json()
    root = Path(event["root_path"])
    result = {
        "event_id": event["id"],
        "count": args.count,
        "elapsed_seconds": round(time.time() - start, 2),
        "captured": dashboard["counts"].get("captured", 0),
        "processed": dashboard["counts"].get("processed", 0),
        "queue": dashboard["counts"].get("queue", 0),
        "failed": dashboard["counts"].get("failed", 0),
        "original_files": len(list((root / "ORIGINAL").glob("*.jpg"))),
        "finished_files": len(list((root / "FINISHED").glob("*.jpg"))),
    }
    print(json.dumps(result, indent=2))
    lost_originals = result["original_files"] < args.count
    return 1 if lost_originals or result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
