import copy
from collections import Counter

import pytest

from lastbean.data import ContentError, load_content, parse_content, read_raw


@pytest.fixture(scope="module")
def raw():
    return read_raw()


@pytest.fixture(scope="module")
def content(raw):
    return parse_content(raw)


def test_content_loads_and_validates():
    load_content()


def test_counts(content):
    assert len(content.characters) == 10
    assert len(content.upgrades) == 50
    rarity = Counter(u.rarity for u in content.upgrades)
    assert rarity == {"common": 18, "uncommon": 14, "rare": 9, "epic": 6, "legendary": 3}
    assert len(content.mobs) == 10
    assert len(content.bosses) == 5
    assert len(content.shrines) == 4
    assert len(content.biomes) == 5
    assert len(content.challenges) == 55
    assert len(content.skins) == 20


def test_phase_one_vertical_slice(content):
    phase1 = lambda items: {x.id for x in items if x.impl_phase == 1}  # noqa: E731
    assert phase1(content.characters) == {"ranger"}
    assert sum(u.impl_phase == 1 for u in content.upgrades) == 12
    assert phase1(content.bosses) == {"ildra"}


def test_typed_lookup(content):
    ranger = content.character("ranger")
    assert ranger.unlock_challenge is None and ranger.weapon.projectile_speed > 0
    assert content.boss("reaper").summon == "altar"
    assert content.balance.boss_waves[10] == "ildra"
    with pytest.raises(KeyError):
        content.mob("does_not_exist")


def broken(raw, mutate):
    data = copy.deepcopy(raw)
    mutate(data)
    with pytest.raises(ContentError) as exc:
        parse_content(data)
    return "\n".join(exc.value.errors)


def test_missing_required_field(raw):
    msg = broken(raw, lambda d: d["characters"][0].pop("hp"))
    assert "characters[ranger]: missing field 'hp'" in msg


def test_value_out_of_range(raw):
    def mutate(d):
        d["characters"][0]["crit_chance"] = 150
        d["upgrades"][0]["rarity"] = "mythic"

    msg = broken(raw, mutate)
    assert "crit_chance: 150 outside" in msg and "'mythic' not in" in msg


def test_wrong_type(raw):
    msg = broken(raw, lambda d: d["mobs"][0].__setitem__("hp", "lots"))
    assert "mobs[slimeling].hp: expected int, got str" in msg


def test_bad_color(raw):
    msg = broken(raw, lambda d: d["style"].__setitem__("ink", "purple"))
    assert "style.ink" in msg


def test_unknown_skin_reference(raw):
    msg = broken(raw, lambda d: d["characters"][0]["skins"].append("nope"))
    assert "unknown skin 'nope'" in msg


def test_unknown_challenge_reference(raw):
    msg = broken(raw, lambda d: d["characters"][1].__setitem__("unlock_challenge", "nope"))
    assert "unknown challenge 'nope'" in msg


def test_challenge_must_grant_what_it_unlocks(raw):
    def mutate(d):
        pyro = next(c for c in d["characters"] if c["id"] == "pyro")
        pyro["unlock_challenge"] = next(c for c in d["characters"] if c["id"] == "rogue")["unlock_challenge"]

    assert "does not reward unlock_character 'pyro'" in broken(raw, mutate)


def test_unknown_reward_target(raw):
    msg = broken(raw, lambda d: d["challenges"][0]["reward"].__setitem__("id", "ghost"))
    assert "references unknown 'ghost'" in msg


def test_mob_with_unknown_biome(raw):
    msg = broken(raw, lambda d: d["mobs"][0]["biome_weights"].__setitem__("moon", 1))
    assert "mob slimeling: unknown biome 'moon'" in msg


def test_boss_wave_mismatch(raw):
    msg = broken(raw, lambda d: d["balance"]["boss_waves"].__setitem__("10", "skarra"))
    assert "boss 'skarra' has spawn_wave 15, not 10" in msg


def test_duplicate_ids(raw):
    msg = broken(raw, lambda d: d["upgrades"].append(copy.deepcopy(d["upgrades"][0])))
    assert "upgrades: duplicate id" in msg


def test_epic_upgrades_start_locked(raw):
    def mutate(d):
        epic = next(u for u in d["upgrades"] if u["rarity"] == "epic")
        epic["unlocked_at_start"], epic["unlock_challenge"] = True, None

    assert "epic/legendary upgrades must start locked" in broken(raw, mutate)


def test_missing_file(tmp_path):
    with pytest.raises(ContentError, match="file missing"):
        read_raw(tmp_path)
