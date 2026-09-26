"""Collect public YouTube captions used to document vendor indicator rules."""
from __future__ import annotations

import json
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi


VIDEOS = {
    "gold_fakeout": "JypPCU-lFv0",
    "13x": "ynUHlFKvfvM",
    "100_pips": "PJbo-h5R2nA",
    "london_box": "bVL6LpD8Su4",
    "nasdaq_gap_drive": "zG9n2TPyesA",
    "duck_duck_duck": "4LFktFxGIBQ",
    "caixa_americana": "jlnIcbO_1cc",
}


def main() -> None:
    destination = Path("output/vendor_indicator_research/transcripts_clean")
    destination.mkdir(parents=True, exist_ok=True)
    api = YouTubeTranscriptApi()
    manifest = []
    for name, video_id in VIDEOS.items():
        transcript = api.fetch(video_id, languages=["pt", "pt-BR"])
        rows = [
            {"start_seconds": round(item.start, 3), "duration_seconds": round(item.duration, 3), "text": item.text}
            for item in transcript
        ]
        path = destination / f"{name}.json"
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append({"name": name, "video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}", "segments": len(rows), "file": str(path)})
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
