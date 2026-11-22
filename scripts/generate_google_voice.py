"""Generate Vietnamese MP3 masters and Windows-ready PCM WAV assets."""

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave

from src.traffic_sign_demo.vietnamese_labels import VIETNAMESE_CLASSES, alert_sentence


ROOT = Path(__file__).resolve().parents[1]


def generate(out: Path, ffmpeg: str) -> None:
    from gtts import gTTS
    from gtts.tts import gTTSError

    if version("gTTS") != "2.5.4":
        raise RuntimeError("Install gTTS==2.5.4 in the asset generation environment.")
    if out.exists():
        raise FileExistsError(f"Choose a new output directory: {out}")
    samples = ROOT / "assets" / "voice_google_samples"
    approved = {
        entry["class_id"]: entry
        for entry in json.loads((samples / "samples.json").read_text(encoding="utf-8"))["samples"]
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    records = {}
    with tempfile.TemporaryDirectory(prefix=".google-voice-", dir=out.parent) as staging:
        stage = Path(staging)
        clips = stage / "clips"
        clips.mkdir()
        for class_id, label in VIETNAMESE_CLASSES.items():
            text = alert_sentence(label)
            mp3 = clips / f"{class_id:02}.mp3"
            wav = clips / f"{class_id:02}.wav"
            if class_id in approved:
                sample = approved[class_id]
                audio = (samples / sample["file"]).read_bytes()
                if sample["sentence"] != text or hashlib.sha256(audio).hexdigest() != sample["sha256"]:
                    raise ValueError(f"Approved sample mismatch for class {class_id}.")
                mp3.write_bytes(audio)
            else:
                for attempt in range(3):
                    try:
                        gTTS(text=text, lang="vi", timeout=(10, 25)).save(str(mp3))
                        break
                    except gTTSError:
                        if attempt == 2:
                            raise
                        time.sleep(attempt + 1)

            subprocess.run(
                [ffmpeg, "-nostdin", "-v", "error", "-xerror", "-i", str(mp3),
                 "-map", "0:a:0", "-c:a", "pcm_s16le", str(wav)],
                check=True,
            )
            with wave.open(str(wav), "rb") as stream:
                duration = stream.getnframes() / stream.getframerate()
                if duration <= 0:
                    raise ValueError(f"Empty clip for class {class_id}.")
            records[class_id] = {
                "text": text, "duration_seconds": round(duration, 3),
                "mp3_sha256": hashlib.sha256(mp3.read_bytes()).hexdigest(),
                "wav_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
                "approved_preview": class_id in approved,
            }
            print(f"{class_id:02} {duration:.2f}s | {text}", flush=True)
        (clips / "provenance.json").write_text(json.dumps({
            "generator": "gTTS 2.5.4", "lang": "vi", "wav_encoding": "FFmpeg PCM s16le",
            "clips": records,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        clips.rename(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--output", type=Path, default=ROOT / "assets" / "voice_google")
    args = parser.parse_args()
    generate(args.output, args.ffmpeg)
