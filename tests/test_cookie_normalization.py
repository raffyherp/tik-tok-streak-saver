import unittest

from streak_saver.modules.utils import normalize_cookie, normalize_cookies


class CookieNormalizationTests(unittest.TestCase):
    def test_browser_extension_cookie_is_converted_for_playwright(self):
        cookie = normalize_cookie({
            "name": "sessionid",
            "value": "secret",
            "domain": ".tiktok.com",
            "path": "/",
            "expirationDate": 1800000000.0,
            "sameSite": "no_restriction",
            "hostOnly": False,
            "storeId": None,
        })
        self.assertEqual(cookie["expires"], 1800000000.0)
        self.assertEqual(cookie["sameSite"], "None")
        self.assertNotIn("expirationDate", cookie)
        self.assertNotIn("hostOnly", cookie)

    def test_session_cookie_drops_expiration(self):
        cookie = normalize_cookie({
            "name": "sid_tt", "value": "secret", "domain": ".tiktok.com",
            "path": "/", "session": True, "expirationDate": 1800000000,
        })
        self.assertNotIn("expires", cookie)

    def test_invalid_entries_are_skipped(self):
        result = normalize_cookies([{"name": "ok", "value": "yes"}, {"name": "missing"}, {}])
        self.assertEqual(result, [{"name": "ok", "value": "yes"}])


if __name__ == "__main__":
    unittest.main()
