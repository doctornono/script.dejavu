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

import pure  # noqa: E402, reportMissingImports


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


class ContextMediaTests(unittest.TestCase):
    def test_normalize_dbtype_aliases(self):
        self.assertEqual(pure.normalize_dbtype("movie"), "movie")
        self.assertEqual(pure.normalize_dbtype("TV"), "tvshow")
        self.assertEqual(pure.normalize_dbtype("tvshow"), "tvshow")
        self.assertEqual(pure.normalize_dbtype("season"), "season")
        self.assertEqual(pure.normalize_dbtype("episode"), "episode")
        self.assertEqual(pure.normalize_dbtype(""), "")
        self.assertEqual(pure.normalize_dbtype("addon"), "")

    def test_normalize_dbtype_from_vstream_scat(self):
        self.assertEqual(pure.normalize_dbtype("", "1"), "movie")
        self.assertEqual(pure.normalize_dbtype("", "2"), "tvshow")
        self.assertEqual(pure.normalize_dbtype("", "3"), "tvshow")
        self.assertEqual(pure.normalize_dbtype("", "9"), "tvshow")
        self.assertEqual(pure.normalize_dbtype("", "4"), "")
        self.assertEqual(pure.normalize_dbtype("movie", "2"), "movie")

    def test_is_context_media(self):
        self.assertTrue(pure.is_context_media({"dbtype": "movie"}))
        self.assertTrue(pure.is_context_media({"dbtype": "tv"}))
        self.assertTrue(pure.is_context_media({"dbtype": "season"}))
        self.assertTrue(pure.is_context_media({"dbtype": "", "s_cat": "1"}))
        self.assertFalse(pure.is_context_media({"dbtype": ""}))
        self.assertFalse(pure.is_context_media({"dbtype": "musicvideo"}))
        self.assertFalse(pure.is_context_media({}))
        self.assertFalse(pure.is_context_media(None))

    def test_api_and_history_types(self):
        self.assertEqual(pure.listitem_api_type("movie"), "movie")
        self.assertEqual(pure.listitem_api_type("tv"), "tv")
        self.assertEqual(pure.listitem_api_type("episode"), "tv")
        self.assertEqual(pure.listitem_api_type(""), "")
        self.assertEqual(pure.listitem_history_type("episode"), "episode")
        self.assertEqual(pure.listitem_history_type("tvshow"), "tv")
        self.assertEqual(pure.listitem_history_type(""), "")

    def test_addons_path(self):
        self.assertTrue(pure.is_addons_path("addons://sources/video/"))
        self.assertTrue(pure.is_addons_path("addons://install/"))
        self.assertFalse(pure.is_addons_path("plugin://plugin.video.vstream/"))
        self.assertFalse(pure.is_addons_path("videodb://movies/titles/"))
        self.assertFalse(pure.is_addons_path(""))

    def test_parse_optional_int(self):
        self.assertEqual(pure.parse_optional_int("12"), 12)
        self.assertEqual(pure.parse_optional_int(0), 0)
        self.assertIsNone(pure.parse_optional_int(-1))
        self.assertIsNone(pure.parse_optional_int(""))
        self.assertIsNone(pure.parse_optional_int(None))


class ContextActionsTests(unittest.TestCase):
    def _ids(self, dbtype, flags=None):
        return [a["id"] for a in pure.context_actions(dbtype, flags)]

    def test_movie_full_empty_status(self):
        self.assertEqual(
            self._ids("movie", {}),
            ["rate", "watched", "watchlist", "favorites", "collection", "list"],
        )
        rate = pure.context_actions("movie", {})[0]
        self.assertEqual(rate["label_id"], 30016)

    def test_movie_stateful_labels(self):
        acts = pure.context_actions("movie", {
            "rating": 8,
            "watched": True,
            "inWatchlist": True,
            "isFavorite": True,
            "inCollection": True,
        })
        self.assertEqual(
            [a["id"] for a in acts],
            ["rate", "unwatched", "rewatch", "watchlist", "favorites", "collection", "list"],
        )
        self.assertEqual(acts[0]["label_id"], 30200)
        self.assertEqual(acts[0]["label_arg"], 8)
        self.assertEqual(acts[1]["label_id"], 30093)
        self.assertEqual(acts[2]["label_id"], 30204)
        self.assertEqual(acts[3]["label_id"], 30201)
        self.assertEqual(acts[4]["label_id"], 30202)
        self.assertEqual(acts[5]["label_id"], 30203)
        self.assertEqual(acts[6]["label_id"], 30101)

    def test_movie_rewatch_with_date_plural(self):
        acts = pure.context_actions("movie", {
            "watched": True,
            "rewatchCount": 3,
            "watched_at_label": "11/09/2026",
        })
        rewatch = [a for a in acts if a["id"] == "rewatch"][0]
        self.assertEqual(rewatch["label_id"], 30206)
        self.assertEqual(rewatch["label_arg"], (3, "11/09/2026"))

    def test_movie_rewatch_with_date_singular(self):
        acts = pure.context_actions("movie", {
            "watched": True,
            "rewatchCount": 1,
            "watched_at_label": "11/09/2026",
        })
        rewatch = [a for a in acts if a["id"] == "rewatch"][0]
        self.assertEqual(rewatch["label_id"], 30207)
        self.assertEqual(rewatch["label_arg"], (1, "11/09/2026"))

    def test_tvshow_full_without_watched(self):
        self.assertEqual(
            self._ids("tv"),
            ["rate", "watchlist", "favorites", "collection", "list"],
        )

    def test_episode_rate_and_both_watched(self):
        self.assertEqual(
            self._ids("episode", {}),
            ["rate", "watched", "unwatched"],
        )
        self.assertEqual(pure.context_actions("episode", {})[0]["label_id"], 30016)

    def test_episode_watched_adds_rewatch(self):
        self.assertEqual(
            self._ids("episode", {"watched": True, "inWatchlist": True}),
            ["rate", "watched", "unwatched", "rewatch"],
        )
        self.assertEqual(
            pure.context_actions("episode", {"watched": True})[-1]["label_id"],
            30204,
        )
        dated = pure.context_actions("episode", {
            "watched": True,
            "rewatchCount": 2,
            "watched_at_label": "01/02/2026",
        })[-1]
        self.assertEqual(dated["label_id"], 30206)
        self.assertEqual(dated["label_arg"], (2, "01/02/2026"))

    def test_season_rate_only(self):
        self.assertEqual(self._ids("season", {"rating": 9, "inWatchlist": True}), ["rate"])
        self.assertEqual(pure.context_actions("season", {"rating": 9})[0]["label_id"], 30016)

    def test_unknown_empty(self):
        self.assertEqual(self._ids(""), [])
        self.assertEqual(self._ids("addon"), [])
        self.assertEqual(pure.context_actions(None), [])


class StripLabelAndPluginIdsTests(unittest.TestCase):
    def test_strip_overlay_badges(self):
        raw = "[COLOR green]✔[/COLOR] The Matrix  ★8  [COLOR yellow]●[/COLOR] [COLOR red]♥[/COLOR]"
        self.assertEqual(pure.strip_kodi_label(raw), "The Matrix")

    def test_ids_from_alkoflix_style_url(self):
        path = "plugin://plugin.video.alkoflix/?action=dejavu_play&type=movie&tmdb_id=603"
        ids = pure.ids_from_plugin_path(path)
        self.assertEqual(ids["tmdb_id"], "603")
        self.assertEqual(ids["media_type"], "movie")

    def test_ids_from_elementum_tmdb_path(self):
        path = "plugin://plugin.video.elementum/movie/tmdb/550/play"
        self.assertEqual(pure.ids_from_plugin_path(path)["tmdb_id"], "550")

    def test_ignores_non_plugin_paths(self):
        self.assertEqual(pure.ids_from_plugin_path("videodb://movies/titles/1")["tmdb_id"], "")


class StatusFlagsTests(unittest.TestCase):
    def test_v1_envelope_movie_key(self):
        result = {"success": True, "data": {"movie:603": {"isFavorite": True, "inWatchlist": False}}}
        flags = pure.status_flags(result, "movie", 603)
        self.assertTrue(flags.get("isFavorite"))
        self.assertFalse(flags.get("inWatchlist"))

    def test_tvshow_alias_uses_tv_key(self):
        result = {"data": {"tv:1396": {"isFavorite": True}}}
        self.assertTrue(pure.status_flags(result, "tvshow", "1396").get("isFavorite"))

    def test_missing_returns_empty(self):
        self.assertEqual(pure.status_flags({"data": {}}, "movie", 1), {})
        self.assertEqual(pure.status_flags(None, "movie", 1), {})

    def test_episode_id_and_season_episode_alias(self):
        result = {
            "data": {
                "episode:62085": {"watched": True, "rewatchCount": 2},
                "episode:1396:1:1": {"watched": True, "rewatchCount": 2},
            }
        }
        self.assertEqual(
            pure.status_flags(result, "episode", 62085).get("rewatchCount"), 2,
        )
        self.assertEqual(
            pure.status_flags(
                result, "episode", "", show_tmdb_id=1396, season=1, episode=1,
            ).get("rewatchCount"),
            2,
        )


class FormatWatchedAtTests(unittest.TestCase):
    def test_iso_to_dmy(self):
        self.assertEqual(
            pure.format_watched_at("2026-09-11T19:00:00.000Z"), "11/09/2026",
        )
        self.assertEqual(pure.format_watched_at("2026-09-11"), "11/09/2026")

    def test_empty_and_garbage(self):
        self.assertEqual(pure.format_watched_at(""), "")
        self.assertEqual(pure.format_watched_at(None), "")
        self.assertEqual(pure.format_watched_at("not-a-date"), "")


if __name__ == "__main__":
    unittest.main()
