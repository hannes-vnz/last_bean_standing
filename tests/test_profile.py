from lastbean.meta.profile import SCHEMA_VERSION, FileProfileStore, MemoryProfileStore


def test_file_store_roundtrip(tmp_path):
    store = FileProfileStore(tmp_path / "sub" / "profile.json")
    assert store.load() == {"schema_version": SCHEMA_VERSION}
    store.save({"schema_version": SCHEMA_VERSION, "stones": 12})
    assert store.load()["stones"] == 12


def test_broken_file_yields_fresh_profile_and_is_kept(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("{not json", encoding="utf-8")
    assert FileProfileStore(path).load() == {"schema_version": SCHEMA_VERSION}
    assert (tmp_path / "profile.broken.json").exists()


def test_memory_store():
    store = MemoryProfileStore()
    store.save({"schema_version": SCHEMA_VERSION, "x": [1]})
    assert store.load()["x"] == [1]
