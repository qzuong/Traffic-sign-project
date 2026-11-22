import io
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.traffic_sign_demo.logging_config import configure_logging


class LoggingConfigurationTests(unittest.TestCase):
    def test_rotating_utf8_file_logs_debug_and_normal_terminal_is_quiet(self):
        with TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "traffic_sign_demo.log"
            terminal = io.StringIO()
            logger = logging.getLogger("traffic_sign_demo_test")
            try:
                with patch("src.traffic_sign_demo.logging_config.sys.stderr", terminal):
                    runtime = configure_logging(debug=False, log_path=log_path)
                    try:
                        logger.debug("Performance AI FPS=2.1 Đang phân tích biển báo")
                        logger.info("Worker READY")
                    finally:
                        runtime.close()

                terminal_output = terminal.getvalue()
                file_output = log_path.read_text(encoding="utf-8")
                self.assertIn("Worker READY", terminal_output)
                self.assertNotIn("Performance AI FPS", terminal_output)
                self.assertIn("Performance AI FPS=2.1 Đang phân tích biển báo", file_output)
                self.assertIn("INFO", file_output)
                self.assertIn("DEBUG", file_output)
                self.assertRegex(file_output, r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")
                self.assertTrue(log_path.is_file())
            finally:
                logger.handlers.clear()
                logger.propagate = True

    def test_debug_mode_writes_diagnostic_records_to_terminal(self):
        with TemporaryDirectory() as temporary_directory:
            terminal = io.StringIO()
            logger = logging.getLogger("traffic_sign_demo_debug_test")
            try:
                with patch("src.traffic_sign_demo.logging_config.sys.stderr", terminal):
                    runtime = configure_logging(
                        debug=True,
                        log_path=Path(temporary_directory) / "traffic_sign_demo.log",
                    )
                    try:
                        logger.debug("Display FPS 28.5; inference latency 420 ms")
                    finally:
                        runtime.close()

                self.assertIn("Display FPS 28.5", terminal.getvalue())
            finally:
                logger.handlers.clear()
                logger.propagate = True


if __name__ == "__main__":
    unittest.main()
