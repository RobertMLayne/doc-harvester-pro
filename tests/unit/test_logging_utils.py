# tests/unit/test_logging_utils.py
import json
import logging

from docharvester_pro import logging_utils


def test_log_record_format(capsys):
    logger = logging_utils.get_logger("test")
    logger.info("hello %s", "world")
    captured = capsys.readouterr().out.strip()
    data = json.loads(captured)
    assert data["msg"] == "hello world"
    assert data["level"] == "info"
    assert data["logger"] == "test"
