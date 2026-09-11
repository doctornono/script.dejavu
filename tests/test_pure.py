# -*- coding: utf-8 -*-
"""Unit tests for resources/lib/pure.py — no xbmc imports."""

import os
import sys
import unittest

LIB = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources", "lib")
)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import pure  # noqa: E402


class UnwrapDataTests(unittest.TestCase):
    def test_unwraps_v1_envelope(self):
        self.assertEqual(pure.unwrap_data({"success": True, "data": {"id": 1}}), {"id": 1})

    def test_passthrough_plain_dict(self):
        payload = {"id": 2}
        self.assertIs(pure.unwrap_data(payload), payload)

    def test_passthrough_none_and_list(self):
        self.assertIsNone(pure.unwrap_data(None))
        self.assertEqual(pure.unwrap_data([1, 2]), [1, 2])


class ExtractIdsTests(unittest.TestCase):
    def test_tmdb_and_imdb_from_uniqueids(self):
        tmdb_id, imdb_id = pure.extract_ids({"tmdb": "603", "imdb": "tt0133093"})
        self.assertEqual(tmdb_id, 603)
        self.assertEqual(imdb_id, "tt0133093")

    def test_themoviedb_alias_and_unknown_tt(self):
        tmdb_id, imdb_id = pure.extract_ids({"themoviedb": "1396", "unknown": "tt0903747"})
        self.assertEqual(tmdb_id, 1396)
        self.assertEqual(imdb_id, "tt0903747")

    def test_imdbnumber_digits_as_tmdb(self):
        tmdb_id, imdb_id = pure.extract_ids({}, imdbnumber="550")
        self.assertEqual(tmdb_id, 550)
        self.assertIsNone(imdb_id)

    def test_non_dict_uniqueids(self):
        tmdb_id, imdb_id = pure.extract_ids(None, imdbnumber="tt0111161")
        self.assertIsNone(tmdb_id)
        self.assertEqual(imdb_id, "tt0111161")


class EffectiveApiUrlTests(unittest.TestCase):
    def test_pins_default_when_empty(self):
        self.assertEqual(pure.effective_api_url(""), pure.DEFAULT_API_URL)

    def test_allows_official_https_host(self):
        self.assertEqual(
            pure.effective_api_url("https://dejavu.plus/api/v1"),
            "https://dejavu.plus/api/v1",
        )

    def test_rejects_http_and_unknown_host(self):
        self.assertEqual(pure.effective_api_url("http://dejavu.plus/api/v1"), pure.DEFAULT_API_URL)
        self.assertEqual(
            pure.effective_api_url("https://evil.example/api"),
            pure.DEFAULT_API_URL,
        )

    def test_debug_allows_custom_https(self):
        self.assertEqual(
            pure.effective_api_url("https://localhost:8443/api/v1", debug=True),
            "https://localhost:8443/api/v1",
        )


class ResultPropertyTests(unittest.TestCase):
    def test_keeps_script_dejavu_prefix(self):
        self.assertEqual(
            pure.sanitize_result_property("get_me", "script.dejavu.get_me.result"),
            "script.dejavu.get_me.result",
        )

    def test_rejects_foreign_prefix(self):
        self.assertEqual(
            pure.sanitize_result_property("get_me", "plugin.video.other.result"),
            "script.dejavu.get_me.result",
        )


class SessionMigrationTests(unittest.TestCase):
    def test_no_resurrection_when_session_json_exists(self):
        self.assertFalse(pure.should_migrate_settings_token(True, ""))
        self.assertFalse(pure.should_migrate_settings_token(True, "sk_alive"))

    def test_migrate_only_when_file_missing_and_no_token(self):
        self.assertTrue(pure.should_migrate_settings_token(False, ""))
        self.assertFalse(pure.should_migrate_settings_token(False, "sk_from_json"))


if __name__ == "__main__":
    unittest.main()
