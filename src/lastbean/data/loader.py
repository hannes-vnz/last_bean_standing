"""Load `data/*.json` into typed structures and validate them.

`load_content()` collects every problem it finds (missing fields, wrong types,
values out of range, broken cross references) and raises one `ContentError`
listing all of them, so a broken data file is reported in one go.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schema import (
    IMPL_PHASES,
    RARITIES,
    Ability,
    Balance,
    Biome,
    Boss,
    Challenge,
    Character,
    Condition,
    Content,
    Mob,
    Mode,
    Reward,
    Shop,
    Shrine,
    Skin,
    Style,
    Upgrade,
    Weapon,
    WorkshopItem,
)


def _find_data_dir() -> Path:
    """`data/` next to `src/` in the repo, or next to the `lastbean` package in the web build."""
    here = Path(__file__).resolve()
    for base in (here.parents[3], here.parents[2]):
        if (base / "data" / "balance.json").is_file():
            return base / "data"
    return here.parents[3] / "data"


DATA_DIR = _find_data_dir()
DATA_FILES = (
    "balance", "biomes", "bosses", "challenges", "characters", "elite", "mobs",
    "modes", "shop", "shrines", "skins", "style", "swarm", "upgrades",
)  # fmt: skip
REWARD_TYPES = ("unlock_character", "unlock_upgrade", "unlock_skin", "unlock_mode", "title")
CONDITION_TYPES = ("run_stat", "profile_stat", "run_flag")
OPS = (">=", ">", "<=", "<", "==")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_MISSING = object()


class ContentError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} content error(s):\n  - " + "\n  - ".join(errors))


class _Reader:
    """Typed field access on one JSON object. Problems are appended to `errors`, never raised."""

    def __init__(self, obj: Any, ctx: str, errors: list[str]) -> None:
        self.ctx, self.errors = ctx, errors
        if not isinstance(obj, dict):
            errors.append(f"{ctx}: object expected, got {type(obj).__name__}")
            obj = {}
        self.obj = obj

    def _get(self, key, types, default, optional):
        v = self.obj.get(key, _MISSING)
        if v is _MISSING or (v is None and optional):
            if not optional:
                self.errors.append(f"{self.ctx}: missing field '{key}'")
            return None if optional else default
        # bool is a subclass of int; never accept it as a number.
        if not isinstance(v, types) or (isinstance(v, bool) and bool not in _as_tuple(types)):
            self.errors.append(f"{self.ctx}.{key}: expected {_type_names(types)}, got {type(v).__name__}")
            return default
        return v

    def _range(self, key, v, lo, hi):
        if v is None:
            return v
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            self.errors.append(f"{self.ctx}.{key}: {v} outside [{lo}, {hi}]")
        return v

    def str(self, key, optional=False, choices=None):
        v = self._get(key, str, "", optional)
        if choices is not None and v is not None and v not in choices:
            self.errors.append(f"{self.ctx}.{key}: '{v}' not in {list(choices)}")
        return v

    def int(self, key, lo=None, hi=None, optional=False):
        return self._range(key, self._get(key, int, 0, optional), lo, hi)

    def num(self, key, lo=None, hi=None, optional=False):
        v = self._get(key, (int, float), 0.0, optional)
        return self._range(key, None if v is None else float(v), lo, hi)

    def bool(self, key):
        return self._get(key, bool, False, False)

    def list(self, key, optional=False):
        v = self._get(key, list, [], optional)
        return [] if v is None else v

    def dict(self, key, optional=False):
        v = self._get(key, dict, {}, optional)
        return {} if v is None else v

    def sub(self, key) -> _Reader:
        return _Reader(self.dict(key), f"{self.ctx}.{key}", self.errors)

    def color(self, key, optional=False):
        v = self.str(key, optional)
        if v and not _HEX.match(v):
            self.errors.append(f"{self.ctx}.{key}: '{v}' is not a #rrggbb color")
        return v

    def phase(self, default=None):
        if default is not None and "impl_phase" not in self.obj:
            return default
        return self.int("impl_phase", min(IMPL_PHASES), max(IMPL_PHASES))


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _as_tuple(t):
    return t if isinstance(t, tuple) else (t,)


def _type_names(t):
    return "/".join(x.__name__ for x in _as_tuple(t))


def _str_list(r: _Reader, key: str) -> tuple[str, ...]:
    items = r.list(key)
    if not all(isinstance(x, str) for x in items):
        r.errors.append(f"{r.ctx}.{key}: list of strings expected")
    return tuple(str(x) for x in items)


def _items(raw: Any, name: str, errors: list[str]) -> list[_Reader]:
    if not isinstance(raw, list):
        errors.append(f"{name}: list expected")
        return []
    out = []
    for i, obj in enumerate(raw):
        ident = obj.get("id") if isinstance(obj, dict) else None
        out.append(_Reader(obj, f"{name}[{ident or i}]", errors))
    return out


# ---------------------------------------------------------------------------- parsers


def _balance(raw, e) -> Balance:
    r = _Reader(raw, "balance", e)
    arena = r.list("arena_tiles")
    if len(arena) != 2 or not all(isinstance(x, int) and x > 0 for x in arena):
        e.append("balance.arena_tiles: two positive ints expected")
        arena = [60, 60]
    boss_waves = {}
    for k, v in r.dict("boss_waves").items():
        if not str(k).isdigit() or not isinstance(v, str):
            e.append(f"balance.boss_waves: bad entry {k!r}: {v!r}")
        else:
            boss_waves[int(k)] = v
    weights = r.dict("rarity_weights")
    if set(weights) != set(RARITIES) or not all(isinstance(w, int) and w >= 0 for w in weights.values()):
        e.append(f"balance.rarity_weights: non-negative int for each of {list(RARITIES)} expected")
    mini = r.list("mini_boss_times_s")
    if not all(isinstance(t, int) and t >= 0 for t in mini):
        e.append("balance.mini_boss_times_s: non-negative ints expected")
    fb = r.sub("final_boss")
    return Balance(
        tick_hz=r.int("tick_hz", 1),
        wave_interval_s=r.int("wave_interval_s", 1),
        max_wave=r.int("max_wave", 1),
        swarm_time_s=r.int("swarm_time_s", 0),
        max_alive_enemies=r.int("max_alive_enemies", 1),
        arena_tiles=(arena[0], arena[1]),
        tile_px=r.int("tile_px", 1),
        boss_waves=boss_waves,
        mini_boss_times_s=tuple(mini),
        rarity_weights=dict(weights),
        level_up_choices=r.int("level_up_choices", 1, 6),
        final_boss_id=fb.str("id"),
        raw=dict(r.obj),
    )


def _ability(r: _Reader, active: bool) -> Ability:
    effects = r.list("effects", optional=active)
    return Ability(
        id=r.str("id"),
        name=r.str("name"),
        text=r.str("text"),
        cooldown_s=r.num("cooldown_s", 0.1) if active else None,
        effects=tuple(effects),
    )


def _character(r: _Reader) -> Character:
    w = r.sub("weapon")
    vfx = r.dict("vfx")
    return Character(
        id=r.str("id"),
        name=r.str("name"),
        title=r.str("title"),
        archetype=r.str("archetype"),
        hp=r.int("hp", 1),
        speed=r.int("speed", 1),
        damage=r.int("damage", 1),
        attack_rate=r.num("attack_rate", 0.01),
        range=r.int("range", 1),
        crit_chance=r.int("crit_chance", 0, 100),
        crit_mult=r.num("crit_mult", 1.0),
        weapon=Weapon(
            type=w.str("type"),
            pattern=w.str("pattern"),
            projectile_speed=w.int("projectile_speed", 0),
            pierce=w.int("pierce", 0),
            aoe_radius=w.int("aoe_radius", 0),
            text=w.str("text"),
        ),
        passive=_ability(r.sub("passive"), active=False),
        active=_ability(r.sub("active"), active=True),
        tags=_str_list(r, "tags"),
        unlock_challenge=r.str("unlock_challenge", optional=True),
        impl_phase=r.phase(),
        skins=_str_list(r, "skins"),
        vfx={str(k): str(v) for k, v in vfx.items()},
    )


def _upgrade(r: _Reader) -> Upgrade:
    effects = r.list("effects")
    if not effects:
        r.errors.append(f"{r.ctx}.effects: at least one effect expected")
    for i, eff in enumerate(effects):
        if not isinstance(eff, dict) or not any(isinstance(eff.get(k), str) for k in ("stat", "special")):
            r.errors.append(f"{r.ctx}.effects[{i}]: object with 'stat' or 'special' expected")
    return Upgrade(
        id=r.str("id"),
        name=r.str("name"),
        rarity=r.str("rarity", choices=RARITIES),
        max_level=r.int("max_level", 1),
        tags=_str_list(r, "tags"),
        text=r.str("text"),
        effects=tuple(effects),
        unlocked_at_start=r.bool("unlocked_at_start"),
        unlock_challenge=r.str("unlock_challenge", optional=True),
        impl_phase=r.phase(),
    )


_MOB_KEYS = {"id", "name", "behavior", "hp", "speed", "damage", "cost", "xp", "min_time_s",
             "biome_weights", "radius", "text", "impl_phase"}  # fmt: skip


def _mob(r: _Reader) -> Mob:
    weights = r.dict("biome_weights")
    if not all(_is_num(w) and w >= 0 for w in weights.values()) or not any(weights.values()):
        r.errors.append(f"{r.ctx}.biome_weights: non-negative numbers with at least one > 0 expected")
    return Mob(
        id=r.str("id"),
        name=r.str("name"),
        behavior=r.str("behavior"),
        hp=r.int("hp", 1),
        speed=r.int("speed", 0),
        damage=r.int("damage", 0),
        cost=r.num("cost", 0.01),
        xp=r.num("xp", 0.0),
        min_time_s=r.int("min_time_s", 0),
        biome_weights={k: float(v) for k, v in weights.items()},
        radius=r.int("radius", 1),
        text=r.str("text"),
        impl_phase=r.phase(),
        extra={k: v for k, v in r.obj.items() if k not in _MOB_KEYS},
    )


_BOSS_KEYS = {"id", "name", "hp", "hp_base", "speed", "damage", "biome", "spawn_wave", "spawn_time_s",
              "summon", "phases", "reward", "first_kill_challenge", "impl_phase"}  # fmt: skip


def _boss(r: _Reader) -> Boss:
    summon = r.str("summon", optional=True)
    hp = r.int("hp_base" if summon else "hp", 1)
    phases = r.list("phases")
    for i, ph in enumerate(phases):
        if not isinstance(ph, dict) or not isinstance(ph.get("at_hp_pct"), int) or not 0 < ph["at_hp_pct"] <= 100:
            r.errors.append(f"{r.ctx}.phases[{i}]: at_hp_pct in (0, 100] expected")
    return Boss(
        id=r.str("id"),
        name=r.str("name"),
        hp=hp,
        speed=r.int("speed", 0),
        damage=r.int("damage", 0),
        biome=r.str("biome", optional=summon is not None),
        spawn_wave=None if summon else r.int("spawn_wave", 1),
        spawn_time_s=None if summon else r.int("spawn_time_s", 0),
        summon=summon,
        phases=tuple(phases),
        reward=r.str("reward"),
        first_kill_challenge=r.str("first_kill_challenge"),
        impl_phase=r.phase(),
        extra={k: v for k, v in r.obj.items() if k not in _BOSS_KEYS},
    )


_BIOME_KEYS = {"id", "name", "effect", "rect_tiles", "text", "objects", "palette", "impl_phase"}


def _biome(r: _Reader) -> Biome:
    rect = r.list("rect_tiles")
    if len(rect) != 4 or not all(isinstance(x, int) and x >= 0 for x in rect):
        r.errors.append(f"{r.ctx}.rect_tiles: four non-negative ints expected")
        rect = [0, 0, 0, 0]
    pal = r.sub("palette")
    palette = {k: pal.color(k, optional=True) for k in pal.obj}
    for k in ("ground", "detail"):
        if not palette.get(k):
            r.errors.append(f"{r.ctx}.palette: color '{k}' required")
    return Biome(
        id=r.str("id"),
        name=r.str("name"),
        effect=r.str("effect"),
        rect_tiles=(rect[0], rect[1], rect[2], rect[3]),
        text=r.str("text", optional=True) or "",
        objects=tuple(r.list("objects", optional=True)),
        palette=palette,
        impl_phase=r.phase(default=1),
        extra={k: v for k, v in r.obj.items() if k not in _BIOME_KEYS},
    )


def _challenge(r: _Reader) -> Challenge:
    c = r.sub("condition")
    ctype = c.str("type", choices=CONDITION_TYPES)
    stat_based = ctype in ("run_stat", "profile_stat")
    cond = Condition(
        type=ctype,
        stat=c.str("stat", optional=not stat_based),
        op=c.str("op", optional=not stat_based, choices=OPS if stat_based else None),
        value=c.num("value", optional=not stat_based),
        extra={k: v for k, v in c.obj.items() if k not in ("type", "stat", "op", "value")},
    )
    if ctype == "run_flag":
        c.str("flag")
    rw = r.sub("reward")
    return Challenge(
        id=r.str("id"),
        text=r.str("text"),
        condition=cond,
        reward=Reward(type=rw.str("type", choices=REWARD_TYPES), id=rw.str("id"), stones=rw.int("stones", 0)),
    )


def _skin(r: _Reader) -> Skin:
    tint = r.list("tint")
    if len(tint) != 3 or not all(isinstance(x, int) and 0 <= x <= 255 for x in tint):
        r.errors.append(f"{r.ctx}.tint: three ints in [0, 255] expected")
        tint = [0, 0, 0]
    return Skin(
        id=r.str("id"),
        character=r.str("character"),
        name=r.str("name"),
        tint=(tint[0], tint[1], tint[2]),
        unlock_challenge=r.str("unlock_challenge"),
    )


def _shrine(r: _Reader) -> Shrine:
    return Shrine(
        id=r.str("id"),
        name=r.str("name"),
        count=r.int("count", 1),
        channel_s=r.num("channel_s", 0.0),
        radius_px=r.int("radius_px", 1),
        difficulty_add=r.num("difficulty_add", 0.0, 1.0),
        impl_phase=r.phase(),
        effect=r.str("effect"),
        reward=r.str("reward"),
    )


def _mode(r: _Reader) -> Mode:
    return Mode(
        id=r.str("id"),
        name=r.str("name"),
        text=r.str("text"),
        hp_mult=r.num("hp_mult", 0.01),
        xp_mult=r.num("xp_mult", 0.01),
        score_mult=r.num("score_mult", 0.01),
        unlock_challenge=r.str("unlock_challenge"),
    )


def _style(raw, e) -> Style:
    r = _Reader(raw, "style", e)

    def colors(key):
        s = r.sub(key)
        return {k: s.color(k) for k in s.obj}

    flowers = r.list("flowers")
    for i, f in enumerate(flowers):
        if not isinstance(f, str) or not _HEX.match(f):
            e.append(f"style.flowers[{i}]: #rrggbb color expected")
    style = Style(
        name=r.str("name"),
        ink=r.color("ink"),
        player=colors("player"),
        enemy=colors("enemy"),
        player_projectile=colors("player_projectile"),
        enemy_projectile=colors("enemy_projectile"),
        xp_orb=r.color("xp_orb"),
        heal_orb=r.color("heal_orb"),
        telegraph=r.color("telegraph"),
        crit_text=r.color("crit_text"),
        reaper=r.color("reaper"),
        flowers=tuple(flowers),
    )
    if "body" not in style.player:
        e.append("style.player: color 'body' required")
    return style


def _shop(raw, e) -> Shop:
    r = _Reader(raw, "shop", e)
    cur = r.sub("currency")
    packs = r.sub("run_packs")
    workshop = []
    for w in _items(r.list("workshop"), "shop.workshop", e):
        workshop.append(
            WorkshopItem(
                id=w.str("id"),
                name=w.str("name"),
                effect=w.dict("effect"),
                max_level=w.int("max_level", 1),
                base_cost=w.int("base_cost", 1),
                text=w.str("text"),
            )
        )
    items = packs.list("items")
    for p in _items(items, "shop.run_packs.items", e):
        p.str("id"), p.int("cost", 1)
    return Shop(
        currency_id=cur.str("id"),
        currency_name=cur.str("name"),
        workshop=tuple(workshop),
        run_packs_max_per_run=packs.int("max_per_run", 0),
        run_packs=tuple(items),
        raw=dict(r.obj),
    )


# ---------------------------------------------------------------------------- cross references


def _unique(name: str, items, e: list[str]) -> set[str]:
    seen: set[str] = set()
    for x in items:
        if x.id in seen:
            e.append(f"{name}: duplicate id '{x.id}'")
        seen.add(x.id)
    return seen


def _cross_check(c: Content, e: list[str]) -> None:
    chars = _unique("characters", c.characters, e)
    ups = _unique("upgrades", c.upgrades, e)
    mobs = _unique("mobs", c.mobs, e)
    bosses = _unique("bosses", c.bosses, e)
    biomes = _unique("biomes", c.biomes, e)
    chals = _unique("challenges", c.challenges, e)
    skins = _unique("skins", c.skins, e)
    modes = _unique("modes", c.modes, e)
    _unique("shrines", c.shrines, e)
    _unique("shop.workshop", c.shop.workshop, e)
    chal = {x.id: x for x in c.challenges}

    def unlocked_by(owner: str, cid: str | None, rtype: str, target: str) -> None:
        if cid is None:
            return
        if cid not in chals:
            e.append(f"{owner}: unknown challenge '{cid}'")
        elif (chal[cid].reward.type, chal[cid].reward.id) != (rtype, target):
            e.append(f"{owner}: challenge '{cid}' does not reward {rtype} '{target}'")

    for ch in c.characters:
        unlocked_by(f"character {ch.id}", ch.unlock_challenge, "unlock_character", ch.id)
        for s in ch.skins:
            if s not in skins:
                e.append(f"character {ch.id}: unknown skin '{s}'")
    starters = [ch.id for ch in c.characters if ch.unlock_challenge is None]
    if not starters:
        e.append("characters: at least one character must be unlocked at start")

    for u in c.upgrades:
        if u.unlocked_at_start == (u.unlock_challenge is not None):
            e.append(f"upgrade {u.id}: unlocked_at_start and unlock_challenge disagree")
        if u.rarity in ("epic", "legendary") and u.unlocked_at_start:
            e.append(f"upgrade {u.id}: epic/legendary upgrades must start locked")
        unlocked_by(f"upgrade {u.id}", u.unlock_challenge, "unlock_upgrade", u.id)

    for s in c.skins:
        if s.character not in chars:
            e.append(f"skin {s.id}: unknown character '{s.character}'")
        elif s.id not in c.character(s.character).skins:
            e.append(f"skin {s.id}: not listed in character '{s.character}'")
        unlocked_by(f"skin {s.id}", s.unlock_challenge, "unlock_skin", s.id)

    for m in c.mobs:
        for b in m.biome_weights:
            if b not in biomes:
                e.append(f"mob {m.id}: unknown biome '{b}'")

    for b in c.bosses:
        if b.biome is not None and b.biome not in biomes:
            e.append(f"boss {b.id}: unknown biome '{b.biome}'")
        if b.first_kill_challenge not in chals:
            e.append(f"boss {b.id}: unknown challenge '{b.first_kill_challenge}'")
        if b.spawn_wave is not None and b.spawn_time_s != b.spawn_wave * c.balance.wave_interval_s:
            e.append(f"boss {b.id}: spawn_time_s does not match spawn_wave x wave_interval_s")
    for wave, bid in c.balance.boss_waves.items():
        if bid not in bosses:
            e.append(f"balance.boss_waves: unknown boss '{bid}'")
        elif c.boss(bid).spawn_wave != wave:
            e.append(f"balance.boss_waves: boss '{bid}' has spawn_wave {c.boss(bid).spawn_wave}, not {wave}")
    if c.balance.final_boss_id not in bosses:
        e.append(f"balance.final_boss: unknown boss '{c.balance.final_boss_id}'")

    for ch in c.challenges:
        r = ch.reward
        target = {"unlock_character": chars, "unlock_upgrade": ups, "unlock_skin": skins, "unlock_mode": modes}
        if r.type in target and r.id not in target[r.type]:
            e.append(f"challenge {ch.id}: reward {r.type} references unknown '{r.id}'")
        x = ch.condition.extra
        refs = (("character", chars), ("boss", bosses), ("biome", biomes))
        for key, known in refs:
            if key in x and x[key] not in known:
                e.append(f"challenge {ch.id}: unknown {key} '{x[key]}'")
        for uid in x.get("ids", []):
            if uid not in ups:
                e.append(f"challenge {ch.id}: unknown upgrade '{uid}'")

    for m in c.modes:
        if m.unlock_challenge not in chals:
            e.append(f"mode {m.id}: unknown challenge '{m.unlock_challenge}'")

    aw, ah = c.balance.arena_tiles
    for b in c.biomes:
        x, y, w, h = b.rect_tiles
        if w <= 0 or h <= 0 or x + w > aw or y + h > ah:
            e.append(f"biome {b.id}: rect_tiles {b.rect_tiles} outside the {aw}x{ah} arena")

    swarm = c.swarm.get("start_s")
    if swarm != c.balance.swarm_time_s:
        e.append(f"swarm.start_s ({swarm}) differs from balance.swarm_time_s ({c.balance.swarm_time_s})")
    mini = tuple(c.elite.get("mini_boss", {}).get("times_s", ()))
    if mini != c.balance.mini_boss_times_s:
        e.append("elite.mini_boss.times_s differs from balance.mini_boss_times_s")
    _ = mobs  # mob ids are only checked for uniqueness so far


# ---------------------------------------------------------------------------- entry point


def read_raw(data_dir: Path | str = DATA_DIR) -> dict[str, Any]:
    """Read every data file as plain JSON. Missing files raise ContentError."""
    data_dir = Path(data_dir)
    raw, errors = {}, []
    for name in DATA_FILES:
        path = data_dir / f"{name}.json"
        try:
            raw[name] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"{path.name}: file missing")
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON ({exc})")
    if errors:
        raise ContentError(errors)
    return raw


def parse_content(raw: dict[str, Any]) -> Content:
    """Build and validate typed content from already-loaded JSON."""
    e: list[str] = []
    shrines_raw = raw.get("shrines", {})
    content = Content(
        balance=_balance(raw.get("balance"), e),
        characters=tuple(_character(r) for r in _items(raw.get("characters"), "characters", e)),
        upgrades=tuple(_upgrade(r) for r in _items(raw.get("upgrades"), "upgrades", e)),
        mobs=tuple(_mob(r) for r in _items(raw.get("mobs"), "mobs", e)),
        bosses=tuple(_boss(r) for r in _items(raw.get("bosses"), "bosses", e)),
        biomes=tuple(_biome(r) for r in _items(raw.get("biomes"), "biomes", e)),
        challenges=tuple(_challenge(r) for r in _items(raw.get("challenges"), "challenges", e)),
        skins=tuple(_skin(r) for r in _items(raw.get("skins"), "skins", e)),
        shrines=tuple(
            _shrine(r)
            for r in _items(shrines_raw.get("shrines") if isinstance(shrines_raw, dict) else None, "shrines", e)
        ),
        modes=tuple(_mode(r) for r in _items(raw.get("modes"), "modes", e)),
        style=_style(raw.get("style"), e),
        shop=_shop(raw.get("shop"), e),
        elite=raw.get("elite") if isinstance(raw.get("elite"), dict) else {},
        swarm=raw.get("swarm") if isinstance(raw.get("swarm"), dict) else {},
    )
    if not e:
        _cross_check(content, e)
    if e:
        raise ContentError(e)
    return content


def load_content(data_dir: Path | str = DATA_DIR) -> Content:
    return parse_content(read_raw(data_dir))
