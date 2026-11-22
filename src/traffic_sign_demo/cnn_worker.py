from __future__ import annotations

import argparse
import base64
import contextlib
import json
import sys
import time

import numpy as np

from .class_mapping import load_class_mapping


def _write_message(message: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--mapping", required=True)
    args = parser.parse_args()
    print(f"CNN worker sys.executable: {sys.executable}", file=sys.stderr, flush=True)

    try:
        mapping = load_class_mapping(args.mapping)
        with contextlib.redirect_stdout(sys.stderr):
            import tensorflow as tf

            tf.config.threading.set_intra_op_parallelism_threads(2)
            tf.config.threading.set_inter_op_parallelism_threads(1)
            model = tf.keras.models.load_model(args.model, compile=False)
            if tuple(model.input_shape[1:]) != (30, 30, 3):
                raise RuntimeError(f"Unexpected CNN input shape: {model.input_shape}.")
            output_count = int(model.output_shape[-1])
            if output_count != len(mapping):
                raise RuntimeError(
                    f"CNN output has {output_count} classes but mapping has {len(mapping)}."
                )
            model(np.zeros((1, 30, 30, 3), dtype=np.float32), training=False)
    except Exception as exc:
        _write_message({"type": "error", "error": f"{type(exc).__name__}: {exc}"})
        return

    _write_message(
        {
            "type": "ready",
            "python": sys.executable,
            "input_shape": list(model.input_shape),
            "output_shape": list(model.output_shape),
        }
    )

    tensor_bytes = 30 * 30 * 3 * np.dtype(np.float32).itemsize
    for line in sys.stdin:
        request = json.loads(line)
        if request.get("operation") == "stop":
            break
        try:
            predict_ms = 0.0
            tensors = []
            for encoded in request["tensors"]:
                raw = base64.b64decode(encoded, validate=True)
                if len(raw) != tensor_bytes:
                    raise ValueError("A preprocessed crop has an invalid byte length.")
                tensor = np.frombuffer(raw, dtype=np.float32).reshape((30, 30, 3))
                if not np.isfinite(tensor).all():
                    raise ValueError("A preprocessed crop contains non-finite pixels.")
                tensors.append(tensor)

            if not tensors:
                classifications: list[dict[str, object]] = []
            else:
                batch = np.stack(tensors)
                predict_started = time.perf_counter()
                with contextlib.redirect_stdout(sys.stderr):
                    predictions = model(batch, training=False).numpy()
                predict_ms = (time.perf_counter() - predict_started) * 1000
                if predictions.shape != (len(tensors), output_count):
                    raise RuntimeError(
                        f"CNN returned unexpected prediction shape {predictions.shape}."
                    )
                classifications = []
                for detection_index, scores in enumerate(predictions):
                    class_id = int(np.argmax(scores))
                    classifications.append(
                        {
                            "detection_index": detection_index,
                            "class_id": class_id,
                            "class_name": mapping[class_id],
                            "score": float(scores[class_id]),
                        }
                    )

            response = {
                "type": "result",
                "session_id": request["session_id"],
                "frame_id": request["frame_id"],
                "timestamp_ms": request["timestamp_ms"],
                "classifications": classifications,
                "predict_ms": predict_ms,
            }
        except Exception as exc:
            response = {
                "type": "error",
                "session_id": request.get("session_id"),
                "frame_id": request.get("frame_id"),
                "error": f"{type(exc).__name__}: {exc}",
            }
        _write_message(response)


if __name__ == "__main__":
    main()
