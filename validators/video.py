from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class VideoValidationResult:
    ok: bool
    duration_seconds: float
    width: int
    height: int
    message: str


def validate_short_video(video_path: Path) -> VideoValidationResult:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(video_path),
    ]

    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        return VideoValidationResult(
            ok=False,
            duration_seconds=0.0,
            width=0,
            height=0,
            message=f"ffprobe error: {process.stderr.strip()}",
        )

    payload = json.loads(process.stdout)
    stream = payload.get("streams", [{}])[0]
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    duration = float(payload.get("format", {}).get("duration", 0.0))

    if width <= 0 or height <= 0:
        return VideoValidationResult(False, duration, width, height, "Не удалось определить размеры видео")

    if height <= width:
        return VideoValidationResult(False, duration, width, height, "Видео должно быть вертикальным (9:16)")

    ratio = width / height
    if abs(ratio - (9 / 16)) > 0.08:
        return VideoValidationResult(False, duration, width, height, "Видео должно быть близким к соотношению 9:16")

    if duration > 60.0:
        return VideoValidationResult(False, duration, width, height, "Длительность должна быть не больше 60 секунд")

    return VideoValidationResult(True, duration, width, height, "OK")
