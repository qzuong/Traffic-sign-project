from __future__ import annotations

from dataclasses import dataclass
import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
import queue
import sys


@dataclass
class LoggingRuntime:
    queue_handler: QueueHandler
    listener: QueueListener
    handlers: tuple[logging.Handler, ...]

    def close(self) -> None:
        self.listener.stop()
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.queue_handler)
        self.queue_handler.close()
        for handler in self.handlers:
            handler.close()


def configure_logging(
    debug: bool = False, log_path: str | Path | None = None
) -> LoggingRuntime:
    destination = (
        Path(log_path)
        if log_path is not None
        else Path(__file__).resolve().parents[2] / "logs" / "traffic_sign_demo.log"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if debug else logging.INFO)
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        destination,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    records: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    queue_handler = QueueHandler(records)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(queue_handler)

    listener = QueueListener(
        records, console, file_handler, respect_handler_level=True
    )
    listener.start()
    return LoggingRuntime(queue_handler, listener, (console, file_handler))
