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
    result = dict(score=4200, kills=1000, difficulty=1.0, bosses=2, sparkles=37)
    assert workshop.payout(result, content.shop, final_boss_won=False) == {"Punkte": 42, "Gefunden": 37}
    won = workshop.payout(dict(result, difficulty=1.25), content.shop, final_boss_won=True)
    assert won == {"Punkte": 50, "Gefunden": 37, "Sieg": 100}


def test_sparkles_drop_in_the_run(content):
    import dataclasses

    from lastbean.sim import PlayerInput
    from lastbean.sim.events import SparklesCollected

    cfg = WorldConfig.from_content(content)
    cfg = dataclasses.replace(cfg, character=dataclasses.replace(cfg.character, hp=10**9))
    w = World(2, cfg)
    events = []
    for _ in range(150 * 60):
        p = w.players[0]
        events += w.step([PlayerInput(0, 0, 0, 0 if p.offer else None)])
    found = [e for e in events if isinstance(e, SparklesCollected)]
    assert found and w.players[0].sparkles == sum(e.amount for e in found) == w.result().sparkles


def test_greenhouse_wonders_and_seeds(content):
    p = new_profile()
    p["sparkles"] = 2500
    base = WorldConfig.from_content(content)
    cfg = workshop.apply_greenhouse(base, p, content.shop)
    assert "sickle" not in {w.id for w in cfg.weapons} and "thorn_twig" in {w.id for w in cfg.weapons}
    for wid in ("wonder_fourth_card", "wonder_weapon_slot", "wonder_second_seed", "wonder_starter", "wonder_chest_key"):
        assert workshop.buy_greenhouse(p, content.shop, "wonders", wid)
    assert workshop.buy_greenhouse(p, content.shop, "seeds", "sickle")
    assert not workshop.buy_greenhouse(p, content.shop, "seeds", "sickle")  # once
    assert p["sparkles"] == 2500 - 400 - 600 - 500 - 300 - 250 - 200
    cfg = workshop.apply_greenhouse(base, p, content.shop)
    assert cfg.level_up_choices == base.level_up_choices + 1 and cfg.weapon_slots == base.weapon_slots + 1
    assert "sickle" in {w.id for w in cfg.weapons}
    assert cfg.economy.chest_price(0) < base.economy.chest_price(0)
    w = World(1, cfg)
    pl = w.players[0]
    assert pl.weapons and pl.stats.revives == 1  # Startpaket and Zweite Saat
    workshop.sell_greenhouse(p, content.shop, "seeds", "sickle")
    assert "sickle" not in p["greenhouse"]["seeds"] and p["sparkles"] == 2500 - 400 - 600 - 500 - 300 - 250
    assert normalize(p)["greenhouse"]["wonders"] == p["greenhouse"]["wonders"]


def test_every_bed_has_its_music(content):
    from lastbean.audio import MUSIC_DIR

    for track in {st.biome for st in content.stages} | {"boss"}:
        assert (MUSIC_DIR / f"{track}.ogg").stat().st_size > 10_000


def test_boss_entrance_and_phase_announcements(content):
    from lastbean.render.effects import INTRO_FRAMES, Effects
    from lastbean.sim.events import BossPhase, BossSpawned

    fx = Effects({"white": (255, 255, 255), "crit": (255, 212, 94)}, {})
    fx.boss_phases = {b.id: [str(ph.get("pattern", "")) for ph in b.phases] for b in content.bosses}
    fx.handle([BossSpawned(1, None, 7, "snail_queen")], {"snail_queen": "Schleimrun, die Schneckenkönigin"})
    assert fx.intro == ["snail_queen", "Schleimrun, die Schneckenkönigin", INTRO_FRAMES]
    for _ in range(INTRO_FRAMES):
        fx.update()
    assert fx.intro is None
    fx.handle([BossPhase(2, None, 7, "snail_queen", 1)])
    assert fx.banner[0] == "Phase 2!" and fx.subtitle[0] == fx.boss_phases["snail_queen"][1]


def test_run_packs_last_one_run(content):
    p = new_profile()
    p["sparkles"] = 200
    assert workshop.buy_pack(p, content.shop, "pack_headstart") and workshop.buy_pack(p, content.shop, "pack_clover")
    assert not workshop.buy_pack(p, content.shop, "pack_map")  # at most two
    assert p["sparkles"] == 100 and p["packs"] == ["pack_headstart", "pack_clover"]
    workshop.return_pack(p, content.shop, "pack_clover")
    assert p["sparkles"] == 140 and p["packs"] == ["pack_headstart"]
    meta = workshop.meta_mods(p, content.shop, ("pack_headstart", "pack_clover"))
    w = World(1, WorldConfig.from_content(content, meta_mods=meta))
    pl = w.players[0]
    assert pl.level == 3 and pl.offer and pl.stats.luck == 10
