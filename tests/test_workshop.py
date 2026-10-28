"""Funkelsteine and the workshop (shop.json): prices, full refunds, bonuses in the run, payout."""

from lastbean.meta import workshop
from lastbean.meta.profile import new_profile, normalize
from lastbean.sim import World, WorldConfig


def _item(content, wid):
    return next(w for w in content.shop.workshop if w.id == wid)


def test_prices_grow_by_half_and_refunds_are_complete(content):
    hp = _item(content, "ws_hp")
    assert [workshop.level_cost(hp, n) for n in (1, 2, 3)] == [50, 75, 112]
    p = new_profile()
    p["sparkles"] = 200
    assert workshop.buy(p, hp) and workshop.buy(p, hp)
    assert not workshop.buy(p, hp)  # 112 > 75 left
    assert p["sparkles"] == 75 and p["workshop"]["ws_hp"] == 2
    assert workshop.refund(p, hp) == 125 and p["sparkles"] == 200 and "ws_hp" not in p["workshop"]
    assert normalize({"sparkles": -5, "workshop": {"ws_hp": "x", "ws_xp": 2}})["workshop"] == {"ws_xp": 2}


def test_workshop_bonuses_reach_the_run(content):
    p = new_profile()
    p["workshop"] = {"ws_hp": 5, "ws_xp": 2, "ws_reroll": 1, "ws_shield": 1, "ws_radar": 1}
    mods = dict(workshop.meta_mods(p, content.shop))
    assert mods["max_hp_pct"] == 15 and mods["xp_gain_pct"] == 6
    plain = World(1, WorldConfig.from_content(content))
    w = World(1, WorldConfig.from_content(content, meta_mods=workshop.meta_mods(p, content.shop)))
    a, b = plain.players[0], w.players[0]
    assert b.stats.max_hp == a.stats.max_hp * 1.15 and b.hp == b.stats.max_hp
    assert b.stats.xp_mult > a.stats.xp_mult and b.rerolls == a.rerolls + 1
    assert b.temp_shield == 20 and w.snapshot().shrine_radar and not plain.snapshot().shrine_radar
    w._recompute(b)  # a level-up keeps the workshop bonus
    assert b.stats.max_hp == a.stats.max_hp * 1.15


def test_payout_follows_shop_json(content):
    result = dict(score=4200, kills=1000, difficulty=1.0, bosses=2, elites=3, chests=4)
    parts = workshop.payout(result, content.shop, final_boss_won=False)
    assert parts == {"Punkte": 42, "Gegner": 15, "Elite": 6, "Bosse": 40, "Truhen": 12}
    won = workshop.payout(dict(result, bosses=3, difficulty=1.25), content.shop, final_boss_won=True)
    assert won["Punkte"] == 50 and won["Bosse"] == 40 and won["Schnitter"] == 200
