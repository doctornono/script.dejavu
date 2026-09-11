# -*- coding: utf-8 -*-
"""SQLite cache tests — no xbmc imports."""

import os
import sys
import tempfile
import unittest

LIB = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources", "lib")
)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

import cache  # noqa: E402, reportMissingImports


class CacheTests(unittest.TestCase):
    def setUp(self):
        handle, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(handle)
        self.path = path
        cache.set_path_for_tests(path)

    def tearDown(self):
        cache.close()
        cache.set_path_for_tests(None)
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_upsert_merge_and_get_many(self):
        cache.upsert_status({"movie:603": {"watched": True}})
        cache.upsert_status({"movie:603": {"inWatchlist": True, "rating": None}})
        rows = cache.get_many(["movie:603", "movie:1"])
        self.assertTrue(rows["movie:603"]["watched"])
        self.assertTrue(rows["movie:603"]["inWatchlist"])
        self.assertNotIn("rating", rows["movie:603"])
        self.assertNotIn("movie:1", rows)

    def test_cached_status_complete_and_miss(self):
        cache.upsert_status({"movie:603": {"watched": True}})
        hit = cache.cached_status([{"type": "movie", "id": 603}])
        self.assertTrue(hit["success"])
        self.assertTrue(hit["data"]["movie:603"]["watched"])
        miss = cache.cached_status([
            {"type": "movie", "id": 603},
            {"type": "movie", "id": 550},
        ])
        self.assertIsNone(miss)

    def test_apply_write_and_clear(self):
        cache.apply_write("add_to_favorites", {"type": "tv", "id": 1396})
        self.assertTrue(cache.get_many(["tv:1396"])["tv:1396"]["isFavorite"])
        cache.clear()
        self.assertEqual(cache.get_many(["tv:1396"]), {})

    def test_plus_features_meta(self):
        cache.remember_plus_feature("sync_cursor", True)
        cache.remember_plus_feature("unknown", True)
        self.assertEqual(cache.plus_features_available(), ["sync_cursor"])
        cache.remember_plus_feature("sync_cursor", False)
        self.assertEqual(cache.plus_features_available(), [])

    def test_cursor_roundtrip(self):
        self.assertEqual(cache.get_cursor("history"), "")
        cache.set_cursor("history", "2026-09-11T19:00:00.000Z")
        self.assertEqual(cache.get_cursor("history"), "2026-09-11T19:00:00.000Z")


if __name__ == "__main__":
    unittest.main()
