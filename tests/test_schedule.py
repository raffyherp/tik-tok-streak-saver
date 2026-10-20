import configparser
from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from streak_saver.modules.schedule import is_send_due


JAKARTA = ZoneInfo("Asia/Jakarta")


def make_config(send_time: str = "20:00", last_send: str = "") -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config["users"] = {"alice": "🔥"}
    config["SETTINGS"] = {
        "default_message": "🔥",
        "send_time": send_time,
        "last_send": last_send,
    }
    return config


class ScheduleTests(unittest.TestCase):
    def test_before_configured_time_is_not_due(self):
        now = datetime(2026, 10, 21, 19, 59, tzinfo=JAKARTA)
        self.assertFalse(is_send_due(make_config("20:00"), now))

    def test_at_or_after_configured_time_is_due(self):
        config = make_config("20:00")
        self.assertTrue(is_send_due(config, datetime(2026, 10, 21, 20, 0, tzinfo=JAKARTA)))
        self.assertTrue(is_send_due(config, datetime(2026, 10, 21, 23, 30, tzinfo=JAKARTA)))

    def test_completed_day_is_not_due_again(self):
        config = make_config("08:15", last_send="2026-10-21")
        now = datetime(2026, 10, 21, 12, 0, tzinfo=JAKARTA)
        self.assertFalse(is_send_due(config, now))

    def test_non_jakarta_time_is_converted_before_comparison(self):
        utc = ZoneInfo("UTC")
        now = datetime(2026, 10, 21, 13, 0, tzinfo=utc)
        self.assertTrue(is_send_due(make_config("20:00"), now))


if __name__ == "__main__":
    unittest.main()
