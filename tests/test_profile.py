import json
from datetime import UTC, datetime

import pytest

from lastbean.meta.profile import (
    SCHEMA_VERSION,
    BrowserProfileStore,
    FileProfileStore,
    MemoryProfileStore,
    export_code,
    import_code,
    new_profile,
    normalize,
    record_run,
    set_nickname,
    valid_nickname,
)
from lastbean.sim import World, WorldConfig, compute_score


def result(score=100, seconds=60, character="ranger", **kw):
    return dict(score=score, seconds=seconds, kills=10, level=2, bosses=0, wave=2, character=character, seed=1, **kw)


def test_new_profile_has_token_and_no_name():
    p = new_profile()
    assert p["schema_version"] == SCHEMA_VERSION and p["nickname"] is None
    assert len(p["token"]) == 32 and new_profile()["token"] != p["token"]


def test_nickname_rules_match_server():
    assert valid_nickname("Hannes") and valid_nickname("Bohne_42") and valid_nickname("Jürgen")
    assert not valid_nickname("x") and not valid_nickname("a" * 17) and not valid_nickname("<script>")
    p = new_profile()
    set_nickname(p, "  Fenn  ")
    assert p["nickname"] == "Fenn"
    with pytest.raises(ValueError):
        set_nickname(p, "!")


def test_record_run_highscores_and_totals():
    p = new_profile()
    day = datetime(2026, 10, 28, tzinfo=UTC)
    assert record_run(p, result(100), day) == {"new_best": True, "new_character_best": True}
    assert record_run(p, result(80), day) == {"new_best": False, "new_character_best": False}
    assert record_run(p, result(100, seconds=50), day)["new_best"]  # tie: shorter run wins
    assert record_run(p, result(90, character="pyro"), day) == {"new_best": False, "new_character_best": True}
    assert p["highscores"]["overall"]["seconds"] == 50 and p["highscores"]["overall"]["date"] == "2026-10-28"
    assert p["totals"] == {"runs": 4, "seconds": 230, "kills": 40, "bosses": 0}
    assert len(p["recent"]) == 4 and p["recent"][0]["character"] == "pyro"


def test_recent_runs_are_capped():
    p = new_profile()
    for i in range(15):
        record_run(p, result(i))
    assert len(p["recent"]) == 10 and p["recent"][0]["score"] == 14


def test_normalize_repairs_bad_data():
    p = normalize({"nickname": "!", "token": 5, "highscores": {"overall": "x"}, "totals": {"runs": -3}, "recent": [1]})
    assert p["nickname"] is None and len(p["token"]) == 32
    assert p["highscores"]["overall"] is None and p["totals"]["runs"] == 0 and p["recent"] == []


def test_export_import_roundtrip():
    p = new_profile()
    set_nickname(p, "Mira")
    record_run(p, result(321))
    code = export_code(p)
    assert code.startswith("LBS1:") and len(code) < 600
    assert import_code(code[:20] + "\n" + code[20:]) == p  # whitespace from copy and paste is ignored
    with pytest.raises(ValueError):
        import_code("LBS1:kaputt")
    with pytest.raises(ValueError):
        import_code("hallo")


def test_file_store_roundtrip(tmp_path):
    store = FileProfileStore(tmp_path / "sub" / "profile.json")
    p = store.load()
    record_run(p, result(7))
    store.save(p)
    assert store.load() == p


def test_broken_file_yields_fresh_profile_and_is_kept(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("{not json", encoding="utf-8")
    assert FileProfileStore(path).load()["highscores"]["overall"] is None
    assert (tmp_path / "profile.broken.json").exists()


def test_memory_store():
    store = MemoryProfileStore()
    p = store.load()
    p["nickname"] = "Kaz"
    store.save(p)
    assert store.load()["nickname"] == "Kaz"


class FakeLocalStorage:
    def __init__(self):
        self.items = {}

    def getItem(self, key):  # noqa: N802 - browser API name
        return self.items.get(key)

    def setItem(self, key, value):  # noqa: N802
        self.items[key] = value


def test_browser_store_uses_local_storage():
    ls = FakeLocalStorage()
    store = BrowserProfileStore(ls)
    p = store.load()
    set_nickname(p, "Aya")
    store.save(p)
    assert json.loads(ls.items[BrowserProfileStore.KEY])["nickname"] == "Aya"
    assert store.load() == p
    ls.items[BrowserProfileStore.KEY] = "{kaputt"
    assert store.load()["nickname"] is None and BrowserProfileStore.KEY + ".broken" in ls.items


def test_score_formula_matches_content(content):
    rules = WorldConfig.from_content(content).score
    assert compute_score(rules, 300, 200, 9, 1) == 2 * 300 + 5 * 200 + 20 * 9 + 500
    assert compute_score(rules, 100, 0, 1, 0, difficulty=1.5) == int((200 + 20) * 1.4)


def test_world_result(make_config):
    w = World(3, make_config(enemy_target=0))
    for _ in range(600):
        w.step()
    r = w.result()
    assert r.seconds == 10 and r.character == "ranger" and r.seed == 3
    assert r.score == 2 * 10 + 20 * 1
