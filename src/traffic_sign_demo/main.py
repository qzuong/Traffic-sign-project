import argparse
import logging
import tkinter as tk

from .desktop_ui import DesktopVideoPlayer
from .inference_service import DEFAULT_DEMO_DETECTOR, DETECTOR_FILES
from .logging_config import configure_logging

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--detector", choices=DETECTOR_FILES, default=DEFAULT_DEMO_DETECTOR)
    parser.add_argument("--debug-seek", action="store_true")
    parser.add_argument("--alert-observations", type=int, choices=range(2, 6))
    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable detailed terminal and file diagnostics",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logging_runtime = configure_logging(args.debug)
    logger.info("Traffic Sign Video Demo 1.1 initialized.")
    try:
        root = tk.Tk()
        DesktopVideoPlayer(
            root,
            image_size=args.imgsz,
            debug_seek=args.debug_seek,
            detector=args.detector,
            **(
                {"alert_observations": args.alert_observations}
                if args.alert_observations
                else {}
            ),
        )
        root.mainloop()
    except Exception:
        logger.exception("Application terminated with an error.")
        raise
    finally:
        logger.info("Traffic Sign Video Demo 1.1 shutting down.")
        logging_runtime.close()


if __name__ == "__main__":
    main()
