"""Game window and main loop.

Fixed simulation step of 1/60 s with an accumulator; rendering runs once per frame.
The loop is async with `await asyncio.sleep(0)` so it also runs in the browser (pygbag).

Debug keys: F3 shows frame timings, F4 switches to a stress test (200 enemies, player cannot die),
F5 runs a synchronous benchmark (independent of the browser frame rate) and shows the result with F3.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import secrets
import sys
import time

import pygame

from .audio import Audio
from .data import load_content
from .meta import challenges, workshop
from .meta.profile import (
    ProfileStore,
    default_store,
    new_profile,
    normalize,
    record_run,
    set_nickname,
    valid_nickname,
)
from .online.account import Account, browser_id_token, browser_passkey, merge, set_passkey_zones
from .online.leaderboard import REFRESH_S, Leaderboard
from .render.effects import Effects
from .render.interp import interpolate
from .render.renderer import CANVAS_H, CANVAS_W, Renderer, effect_palette
from .sim import DT, PlayerInput, World, WorldConfig
from .ui import screens
from .ui.layout import SHORT_SIDE, default_short_side, is_compact, logical_size, pixel_perfect_size, zoom_step
from .ui.touch import TouchState

MAX_STEPS_PER_FRAME = 3  # avoid the spiral of death after a stall (slow devices slow down instead)
WEB = sys.platform == "emscripten"
STRESS_ENEMIES = 200


def read_input(player_id: int = 0) -> PlayerInput:
    keys = pygame.key.get_pressed()
    mx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
    my = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
    ability = bool(keys[pygame.K_SPACE] or keys[pygame.K_e])
    return PlayerInput(player_id, int(mx), int(my), ability=ability)


def card_choice(key: int, renderer: Renderer) -> int | None:
    """Keys on the level-up screen: 1/2/3 pick directly, arrows move the selection, Enter/Space confirm."""
    if key in (pygame.K_1, pygame.K_2, pygame.K_3):
        return key - pygame.K_1
    if key in (pygame.K_LEFT, pygame.K_a):
        renderer.selected = max(0, renderer.selected - 1)
    elif key in (pygame.K_RIGHT, pygame.K_d):
        renderer.selected += 1  # clamped to the number of cards when drawn
    elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
        return renderer.selected
    return None


def benchmark(content, renderer: Renderer, enemies: int = STRESS_ENEMIES, ticks: int = 600) -> str:
    """Simulate `ticks` steps with `enemies` alive and draw 120 frames; report ms per step and per frame."""
    world = World(1, stress_config(WorldConfig.from_content(content), enemies))
    for _ in range(180):  # fill the arena first
        world.step([PlayerInput(0, choice=0)])
    t0 = time.perf_counter()
    for i in range(ticks):
        world.step([PlayerInput(0, 1 if (i // 60) % 2 else -1, 0, choice=0)])
    sim = (time.perf_counter() - t0) / ticks
    t1 = time.perf_counter()
    for _ in range(120):
        renderer.draw(world.snapshot())
    draw = (time.perf_counter() - t1) / 120
    return f"Messlauf {len(world.enemies)} Gegner: sim {sim * 1000:.2f} ms/Schritt, Zeichnen {draw * 1000:.2f} ms/Bild"


def use_whole_page() -> None:
    """pygbag sizes the canvas to half the page until main.py returns, which a game loop never does."""
    try:
        import platform

        platform.window.config.gui_divider = 1
        platform.window.window_resize()
        splash = platform.document.getElementById("lbs-splash")
        if splash:
            splash.style.display = "none"  # the game's own start screen takes over
    except Exception as exc:  # noqa: BLE001 - layout tweak only, never stop the game
        print("Vollbreite nicht gesetzt:", exc)


def stress_config(config: WorldConfig, enemies: int = STRESS_ENEMIES) -> WorldConfig:
    immortal = dataclasses.replace(config.character, hp=10**9)
    return dataclasses.replace(config, character=immortal, enemy_target=enemies)


class FrameTimer:
    """Rolling averages of simulation time, drawing time and frame time, for the F3 overlay."""

    def __init__(self, n: int = 60) -> None:
        self.n = n
        self.samples: dict[str, list[float]] = {"sim": [], "draw": [], "frame": []}

    def add(self, **values: float) -> None:
        for key, v in values.items():
            lst = self.samples[key]
            lst.append(v)
            if len(lst) > self.n:
                lst.pop(0)

    def ms(self, key: str) -> float:
        lst = self.samples[key]
        return 1000 * sum(lst) / max(1, len(lst))

    def text(self, world: World) -> str:
        frame = self.ms("frame")
        fps = 1000 / frame if frame > 0 else 0
        return (
            f"FPS {fps:.0f}  sim {self.ms('sim'):.1f} ms  draw {self.ms('draw'):.1f} ms  "
            f"Gegner {len(world.enemies)}  Kugeln {len(world.orbs)}"
        )


class Game:
    """Screens and the running world. States: "name" -> "menu" -> "play" -> "results" -> "play"/"menu"."""

    def __init__(self, content, renderer: Renderer, store: ProfileStore, seed: int | None, autostart: bool) -> None:
        self.content, self.renderer, self.store = content, renderer, store
        try:
            self.profile = store.load()
        except Exception as exc:  # noqa: BLE001 - a broken store must not stop the game
            print("Spielstand konnte nicht geladen werden:", exc)
            self.profile = new_profile()
        # Only Fenn is there from the start; every other bean comes with its challenge (Paket K).
        self.all_characters = [c for c in content.characters if c.impl_phase in (1, 3)]
        self.starters = sum(1 for c in self.all_characters if not c.unlock_challenge)
        unlocked = self.profile.setdefault("unlocked", {"upgrades": [], "characters": [], "modes": []})["characters"]
        for c in self.all_characters:  # beans someone already played before they were locked stay theirs
            if c.unlock_challenge and c.id not in unlocked and c.id in self.profile["highscores"]["by_character"]:
                unlocked.append(c.id)
        challenges.sync_unlocks(self.profile, content.challenges)  # rewards that changed after they were earned
        playable = {c.id for c in self.characters}
        self.character = self.profile.get("character") if self.profile.get("character") in playable else "ranger"
        self.normal = self._world_config(self.character)
        self.config = self.normal
        renderer.character_sprite = self.character
        self.apply_skin()
        self.fixed_seed = seed
        self.seed = seed if seed is not None else secrets.randbelow(2**31)
        self.world = World(self.seed, self.config)
        self.result: dict = {}
        self.flags: dict = {}
        self.name_buffer = ""
        self.name_upper = True  # on-screen keyboard: capital letter first, then small ones
        if autostart:
            self.state = "play"
        elif not self.profile.get("prologue_seen"):
            self.state = "prologue"  # first start: the short story, then the name
        else:
            self.state = "menu" if self.profile.get("nickname") else "name"
        self.first_name = not self.profile.get("nickname")
        self.settings_return = "menu"
        self.challenge_page = 0
        self.poke_ms = -10_000
        self.squish_ms = -10_000
        self.mode = "normal"  # modes.json; "eternal_night" once its challenge is done
        self.recording = True  # stress-test runs are not recorded
        self.workshop_tab = "wonders"  # greenhouse tab: wonders, seeds, workshop (Kraft), packs (Vorrat)
        self.leaderboard = Leaderboard()
        self.account = Account()
        self.acc_form = {"acc_name": "", "acc_pw": ""}
        self.acc_status = ""
        self.acc_config: dict = {}
        self.text_target = "nickname"  # what the text entry fills: nickname, acc_name or acc_pw
        self.pk_begin: dict[str, dict] = {}  # passkey challenges fetched ahead (Safari wants the dialog in the tap)
        self._pk_zones = ""
        self.online: tuple[str, int | None, int | None] = ("", None, None)
        self.board: dict = {"period": "all", "mode": "normal", "entries": None, "loading": False, "fetched_at": 0.0}
        self._tasks: dict[str, asyncio.Future] = {}

    @property
    def characters(self) -> list:
        """Playable beans: the starters and every unlocked one."""
        unlocked = set(self.profile.get("unlocked", {}).get("characters", []))
        return [c for c in self.all_characters if not c.unlock_challenge or c.id in unlocked]

    def choose_character(self, cid: str) -> None:
        """Pick the bean for the next runs (remembered in the profile)."""
        if cid not in {c.id for c in self.characters}:
            return
        self.character = cid
        self.profile["character"] = cid
        self.save()
        self.normal = self.config = self._world_config(cid)
        self.renderer.character_sprite = cid
        self.apply_skin()

    def _world_config(self, cid: str, packs: tuple[str, ...] = ()) -> WorldConfig:
        """Config for runs with this bean: workshop bonuses, greenhouse wonders and seeds, run packs."""
        meta = workshop.meta_mods(self.profile, self.content.shop, packs)
        unlocked = tuple(self.profile.get("unlocked", {}).get("upgrades", []))  # challenge rewards
        cfg = WorldConfig.from_content(self.content, cid, meta_mods=meta, mode=getattr(self, "mode", "normal"),
                                       unlocked_upgrades=unlocked)  # fmt: skip
        return workshop.apply_greenhouse(cfg, self.profile, self.content.shop)

    def toggle_mode(self) -> None:
        """Normal <-> eternal night (once unlocked); counts from the next run."""
        if "eternal_night" not in self.profile.get("unlocked", {}).get("modes", []):
            return
        self.mode = "eternal_night" if self.mode == "normal" else "normal"
        self.apply_workshop()

    def skin_choices(self) -> list:
        """Unlocked skins of the chosen bean (None = its normal look first)."""
        owned = set(self.profile.get("skins", []))
        return [None] + [s for s in self.content.skins if s.character == self.character and s.id in owned]

    def next_skin(self) -> None:
        choices = self.skin_choices()
        current = self.profile.setdefault("skin", {}).get(self.character)
        ids = [s.id if s else None for s in choices]
        nxt = ids[(ids.index(current) + 1) % len(ids)] if current in ids else ids[0]
        if nxt is None:
            self.profile["skin"].pop(self.character, None)
        else:
            self.profile["skin"][self.character] = nxt
        self.save()
        self.apply_skin()

    def apply_skin(self) -> None:
        sid = self.profile.get("skin", {}).get(self.character)
        skin = next((s for s in self.content.skins if s.id == sid), None)
        self.renderer.character_tint = tuple(skin.tint) if skin else None

    def workshop_action(self, kind: str, item_id: str) -> None:
        item = next((w for w in self.content.shop.workshop if w.id == item_id), None)
        if item is None:
            return
        if kind == "ws_buy":
            workshop.buy(self.profile, item)
        else:
            workshop.refund(self.profile, item)
        self.save()

    def apply_workshop(self) -> None:
        """New bonuses count from the next run on."""
        stress = self.config is not self.normal
        self.normal = self._world_config(self.character)
        if not stress:
            self.config = self.normal

    def change_setting(self, key: str) -> None:
        """Settings screen buttons: volume steps 100-75-50-25-0, switches toggle."""
        s = self.profile["settings"]
        if key == "volume":
            s["volume"] = (s["volume"] - 25) % 125
        elif key in ("numbers", "shake"):
            s[key] = not s[key]
        elif key == "hints":
            self.profile["hints_seen"] = False
        self.save()

    def new_run(self) -> None:
        self.seed = self.seed + 1 if self.fixed_seed is not None else secrets.randbelow(2**31)
        config = self.config
        packs = tuple(self.profile.get("packs", []))
        if packs and self.config is self.normal:  # run packs count for this run only, then they are used up
            config = self._world_config(self.character, packs)
            self.profile["packs"] = []
            self.save()
        self.recording = self.config is self.normal
        self.world = World(self.seed, config)
        self.state = "play"

    def finish_run(self) -> None:
        """Record the result once, when the run ends (stress-test runs are not recorded)."""
        self.result = self.world.result().to_dict()
        self.flags = {}
        self.online = ("", None, None)
        if self.recording:
            self.flags = record_run(self.profile, self.result)
            challenges.record_lifetime(self.profile, self.result)
            new = challenges.evaluate(self.profile, self.result, self.content.challenges, self.starters)
            names = challenges.reward_names(self.content)
            self.result["challenges"] = [(ch.text, challenges.reward_text(ch, names)) for ch in new]
            self.result["epitaph"] = epitaph(self.result, self.content, self.profile.get("nickname"))
            earned = workshop.payout(self.result, self.content.shop, self.world.victory)
            self.result["sparkles"] = earned
            self.profile["sparkles"] = self.profile.get("sparkles", 0) + sum(earned.values())
            if self.leaderboard.queue(self.profile, self.result):
                self.online = ("sending", None, None)
            self.save()
            self.start_sync()
            self.start_cloud_push()
        self.state = "results"

    # ------------------------------------------------------------------ online leaderboard

    def start_sync(self) -> None:
        """Send queued runs in the background (an asyncio task, no threads)."""
        if self.leaderboard.enabled and self.profile["pending_submissions"] and not self._busy("sync"):
            self._tasks["sync"] = asyncio.ensure_future(self._sync())

    async def _sync(self) -> None:
        report = await self.leaderboard.sync(self.profile)
        self.save()
        if report.last_rank:
            self.online = ("rank", report.last_rank, report.last_rank_character)
        elif report.offline and self.online[0] == "sending":
            self.online = ("offline", None, None)
        elif report.error and self.online[0] == "sending":
            self.online = (f"Nicht angenommen: {report.error}", None, None)

    def open_board(self) -> None:
        self.state = "board"
        self.refresh_board()

    def refresh_board(self) -> None:
        if self.leaderboard.enabled and not self._busy("board"):
            self.board["loading"] = True
            self._tasks["board"] = asyncio.ensure_future(self._fetch_board())

    async def _fetch_board(self) -> None:
        self.board["entries"] = await self.leaderboard.top(self.board["period"], mode=self.board["mode"])
        self.board["loading"] = False
        self.board["fetched_at"] = time.monotonic()

    def switch_period(self, step: int) -> None:
        periods = list(screens.PERIOD_NAMES)
        i = periods.index(self.board["period"])
        self.board["period"] = periods[(i + step) % len(periods)]
        self.board["entries"] = None
        self.refresh_board()

    def _busy(self, name: str) -> bool:
        task = self._tasks.get(name)
        return task is not None and not task.done()

    # ------------------------------------------------------------------ account and cloud save

    @property
    def signed_in(self) -> bool:
        return bool(self.profile.get("account", {}).get("session"))

    def open_account(self) -> None:
        self.state, self.acc_status = "account", ""
        if self.account.enabled and not self.acc_config and not self._busy("acc_config"):
            self._tasks["acc_config"] = asyncio.ensure_future(self._load_acc_config())
        self.prefetch_passkeys()

    def prefetch_passkeys(self) -> None:
        if WEB and self.account.enabled and not self._busy("pk_prefetch"):
            self._tasks["pk_prefetch"] = asyncio.ensure_future(self._prefetch_passkeys())

    async def _prefetch_passkeys(self) -> None:
        for purpose in ("login", "register"):
            if purpose not in self.pk_begin:
                begin = await self.account.passkey_begin(purpose)
                if begin:
                    self.pk_begin[purpose] = begin

    def passkey_zones(self, buttons: list, screen) -> None:
        """Tell the page where the passkey buttons are, with their prepared challenges (see online/account.py)."""
        if not WEB:
            return
        zones = []
        if self.state == "account":
            r = self.renderer
            ww, wh = screen.window.get_size()
            user = self.profile.get("nickname") or "Bohne"
            for b in buttons:
                purpose = {"acc_pk_login": "login", "acc_pk_new": "register", "acc_pk_add": "register"}.get(b.action)
                if purpose and purpose in self.pk_begin:
                    k = r._scale
                    x, y = r._dest[0] + b.rect.x * k, r._dest[1] + b.rect.y * k
                    begin = json.dumps(self.pk_begin[purpose])
                    zones.append({"x": x / ww, "y": y / wh, "w": b.rect.w * k / ww, "h": b.rect.h * k / wh,
                                  "purpose": purpose, "begin": begin, "user": user})  # fmt: skip
        key = json.dumps(zones)
        if key != self._pk_zones:
            self._pk_zones = key
            set_passkey_zones(zones)

    async def _load_acc_config(self) -> None:
        self.acc_config = await self.account.config()

    def start_text_entry(self, target: str) -> None:
        """Type the account name or password (same screen as the nickname, with the on-screen keyboard)."""
        self.text_target = target
        self.name_buffer = self.acc_form.get(target, "")
        self.name_upper = target == "acc_name" and not self.name_buffer
        self.state = "name"
        if not WEB:
            pygame.key.start_text_input()

    def account_action(self, action: str) -> None:
        if self._busy("account"):
            return
        if action in ("acc_login", "acc_register"):
            name, pw = self.acc_form["acc_name"].strip(), self.acc_form["acc_pw"]
            if not valid_nickname(name) or len(pw) < 6:
                self.acc_status = "Name (2 bis 16 Zeichen) und Passwort (ab 6 Zeichen) eingeben"
                return
            kind = "login" if action == "acc_login" else "register"
            body = {"name": name, "password": pw}
            self._tasks["account"] = asyncio.ensure_future(self._sign_in(kind, body, "password"))
        elif action in ("acc_pk_login", "acc_pk_new", "acc_pk_add"):
            purpose = "login" if action == "acc_pk_login" else "register"
            attach = action == "acc_pk_add"
            self._tasks["account"] = asyncio.ensure_future(self._passkey(purpose, attach))
        elif action in ("acc_google", "acc_apple"):
            provider = action[4:]
            self._tasks["account"] = asyncio.ensure_future(self._sign_in_with(provider))
        elif action == "acc_sync":
            self._tasks["account"] = asyncio.ensure_future(self._push_cloud(report=True))
        elif action == "acc_logout":
            self._tasks["account"] = asyncio.ensure_future(self._sign_out())

    async def _sign_in_with(self, provider: str) -> None:
        client_id = self.acc_config.get(f"{provider}_client_id", "")
        if not client_id:
            self.acc_status = "Diese Anmeldung ist noch nicht eingerichtet"
            return
        self.acc_status = "Anmeldefenster ist offen ..."
        token = await browser_id_token(provider, client_id)
        if not token:
            self.acc_status = "Anmeldung abgebrochen"
            return
        await self._sign_in("oauth", {"provider": provider, "id_token": token}, provider)

    async def _passkey(self, purpose: str, attach: bool) -> None:
        """Face ID / Touch ID / fingerprint: sign in with a passkey, make one (new account) or add one."""
        begin = self.pk_begin.pop(purpose, None) or await self.account.passkey_begin(purpose)
        if begin is None:
            self.acc_status = "Server nicht erreichbar"
            return
        self.acc_status = "Passkey-Fenster ist offen ..."
        data, error = await browser_passkey(purpose, begin, self.profile.get("nickname") or "Bohne")
        self.prefetch_passkeys()
        if data is None:
            self.acc_status = error
            return
        session = self.profile.get("account", {}).get("session") if attach else None
        res, error = await self.account.passkey_finish(purpose, data, session)
        if res is None:
            self.acc_status = error
            return
        if attach:
            self.acc_status = "Passkey hinzugefügt: ab jetzt geht die Anmeldung per Face ID"
            return
        await self._signed_in(res, "passkey")

    async def _sign_in(self, kind: str, body: dict, provider: str) -> None:
        self.acc_status = "Verbinde ..."
        data, error = await self.account.sign_in(kind, body)
        if data is None:
            self.acc_status = error
            return
        await self._signed_in(data, provider)

    async def _signed_in(self, data: dict, provider: str) -> None:
        self.profile["account"] = {"session": data["session"], "name": data.get("name"), "provider": provider,
                                   "synced_at": 0}  # fmt: skip
        self.acc_form["acc_pw"] = ""
        status, cloud = await self.account.load(data["session"])
        if cloud is not None:  # this device and the cloud become one profile
            account = self.profile["account"]
            self.profile = normalize(merge(self.profile, cloud))
            self.profile["account"] = account
            self.after_profile_change()
        await self._push_cloud()
        self.acc_status = "Angemeldet, Spielstand ist in der Cloud"

    async def _push_cloud(self, report: bool = False) -> None:
        acc = self.profile.get("account")
        if not acc:
            return
        status = await self.account.store(acc["session"], self.profile)
        if status == 200:
            acc["synced_at"] = int(time.time())
            self.save()
            if report:
                self.acc_status = "Gesichert"
        elif status == 401:  # session ended on the server
            self.profile.pop("account", None)
            self.save()
            self.acc_status = "Bitte neu anmelden"
        elif report:
            self.acc_status = "Server nicht erreichbar, später nochmal"

    async def _sign_out(self) -> None:
        acc = self.profile.pop("account", None)
        self.save()
        if acc:
            await self.account.sign_out(acc["session"])
        self.acc_status = "Abgemeldet (der Spielstand bleibt auf diesem Gerät)"

    def start_cloud_push(self) -> None:
        if self.signed_in and self.account.enabled and not self._busy("cloud"):
            self._tasks["cloud"] = asyncio.ensure_future(self._push_cloud())

    def after_profile_change(self) -> None:
        """Bonuses, skin and bean may have changed (cloud save merged in)."""
        self.save()
        if self.character not in {c.id for c in self.characters}:
            self.character = "ranger"
        self.apply_workshop()
        self.apply_skin()

    def save(self) -> None:
        try:
            self.store.save(self.profile)
        except Exception as exc:  # noqa: BLE001 - a full disk or blocked storage must not crash the game
            print("Spielstand konnte nicht gespeichert werden:", exc)

    def start_name_entry(self) -> None:
        self.name_buffer = self.profile.get("nickname") or ""
        self.name_upper = not self.name_buffer
        self.state = "name"
        if not WEB:
            pygame.key.start_text_input()

    def confirm_name(self) -> None:
        if self.text_target != "nickname":  # account name or password
            self.acc_form[self.text_target] = self.name_buffer
            self.text_target, self.state = "nickname", "account"
            pygame.key.stop_text_input()
            return
        if valid_nickname(self.name_buffer):
            set_nickname(self.profile, self.name_buffer)
            self.save()
            self.first_name = False
            self.state = "menu"
            pygame.key.stop_text_input()

    def press_key(self, key: str) -> None:
        """A key of the on-screen keyboard (touch devices)."""
        if key == "shift":
            self.name_upper = not self.name_upper
        elif key == "back":
            self.name_buffer = self.name_buffer[:-1]
            self.name_upper = not self.name_buffer
        elif len(self.name_buffer) < (32 if self.text_target == "acc_pw" else 16):
            self.name_buffer += key
            self.name_upper = key == " "  # after a space the next word starts with a capital

    def type_name(self) -> None:
        """Phones and tablets: the browser's own text dialog brings up the on-screen keyboard."""
        if not WEB:
            return
        answer = web_prompt("Wie heißt deine Bohne? (2 bis 16 Zeichen)", self.name_buffer)
        if answer is not None:
            self.name_buffer = answer.strip()[:16]
            self.confirm_name()

    def handle_name_event(self, event) -> None:
        if event.type == pygame.TEXTINPUT:
            self.name_buffer = (self.name_buffer + event.text)[: 32 if self.text_target == "acc_pw" else 16]
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.name_buffer = self.name_buffer[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm_name()
            elif event.key == pygame.K_ESCAPE and not self.first_name:
                self.state = "menu" if self.text_target == "nickname" else "account"
                self.text_target = "nickname"
                pygame.key.stop_text_input()


def web_prompt(question: str, default: str) -> str | None:
    try:
        import platform

        answer = platform.window.prompt(question, default)
        return None if answer is None else str(answer)
    except Exception as exc:  # noqa: BLE001 - no dialog available: keep the current name
        print("Eingabedialog nicht verfügbar:", exc)
        return None


class Screen:
    """The browser page or desktop window, and the logical canvas size that fits it."""

    def __init__(self, renderer: Renderer, zoom: int | None = None) -> None:
        self.renderer = renderer
        self.window: pygame.Surface | None = None
        self._css = (0, 0)
        self.zoom = zoom  # short side of the canvas chosen by the player; None = device default
        self.fit()

    def default_short(self) -> int:
        """Shorter canvas side without a player zoom (phones start a little closer)."""
        if WEB:
            return default_short_side(is_compact(*self._css[0]))
        return SHORT_SIDE

    def change_zoom(self, steps: int) -> bool:
        """Zoom in (negative steps) or out. Returns True when the view changed."""
        before = (self.renderer.w, self.renderer.h)
        current = self.zoom or min(before)
        # On the web only whole pixel scales exist, so keep stepping until the view really changes.
        for _ in range(4):
            new = zoom_step(current, steps)
            if new == current:
                return (self.renderer.w, self.renderer.h) != before
            self.zoom = current = new
            self.fit(force=True)
            if (self.renderer.w, self.renderer.h) != before:
                return True
        return False

    def css_size(self) -> tuple[int, int]:
        """Size of the canvas element on the page (for mapping taps)."""
        import platform

        canvas = platform.document.getElementById("canvas")
        w, h = (int(canvas.clientWidth), int(canvas.clientHeight)) if canvas else (0, 0)
        if w < 50 or h < 50:
            w, h = self.page_size()
        return w, h

    def page_size(self) -> tuple[int, int]:
        """Visible page in CSS pixels. documentElement is right even when innerWidth/innerHeight are not
        (an iPhone home-screen app started in portrait, until the first rotation)."""
        import platform

        doc = platform.document.documentElement
        w, h = int(doc.clientWidth or 0), int(doc.clientHeight or 0)
        if w < 50 or h < 50:
            w, h = int(platform.window.innerWidth), int(platform.window.innerHeight)
        return w, h

    def fit(self, force: bool = False) -> None:
        """Pick the canvas size for the current screen. On the web the page size is polled (rotation)."""
        if WEB:
            import platform

            css = self.page_size()
            dpr = float(platform.window.devicePixelRatio or 1.0)
            if (css, dpr) == self._css and not force:
                return
            self._css = (css, dpr)
            short = self.zoom or default_short_side(is_compact(*css))
            w, h, k = pixel_perfect_size(*css, dpr, short)
            # Drawing buffer = canvas size, shown at exactly k x k device pixels per canvas pixel
            # (CSS size set below), so pixels and letters stay even and sharp.
            self.window = pygame.display.set_mode((w, h))
            use_whole_page()
            try:
                canvas = platform.document.getElementById("canvas")
                canvas.style.width = f"{w * k / dpr}px"
                canvas.style.height = f"{h * k / dpr}px"
            except Exception as exc:  # noqa: BLE001 - layout tweak only, never stop the game
                print("Canvas-Größe nicht gesetzt:", exc)
            self.renderer.safe = self.safe_insets(css, (w * k / dpr, h * k / dpr), dpr / k)
        else:
            if self.window is None:
                self.window = pygame.display.set_mode((CANVAS_W * 2, CANVAS_H * 2), pygame.RESIZABLE)
            w, h = logical_size(*self.window.get_size(), short=self.zoom)
        self.renderer.resize(w, h)

    def safe_insets(self, page: tuple[int, int], canvas_css: tuple[float, float], px_per_css: float):
        """The phone's safe area (notch, Dynamic Island, home bar) as canvas pixels inside the canvas."""
        import platform

        try:
            platform.window.eval(SAFE_AREA_JS)
            top, right, bottom, left = (float(v) for v in str(platform.window.lbsSafe).split(","))
        except Exception as exc:  # noqa: BLE001 - layout tweak only
            print("Safe Area unbekannt:", exc)
            return (0, 0, 0, 0)
        ox, oy = (page[0] - canvas_css[0]) / 2, (page[1] - canvas_css[1]) / 2  # canvas is centred on the page
        return tuple(
            max(0, round((v - off) * px_per_css)) for v, off in ((top, oy), (right, ox), (bottom, oy), (left, ox))
        )

    def debug_requested(self) -> bool:
        """Web: `?debug` in the address shows touch diagnostics on screen (for testing on phones)."""
        if not WEB:
            return False
        try:
            import platform

            return "debug" in str(platform.window.location.search)
        except Exception:  # noqa: BLE001
            return False

    def to_canvas(self, event) -> tuple[int, int]:
        """Canvas position of a mouse or finger event (fingers come normalised to 0..1)."""
        ww, wh = self.window.get_size()
        if event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            nx, ny = event.x, event.y
        else:
            nx, ny = event.pos[0] / ww, event.pos[1] / wh
        if WEB:
            nx, ny = contain_point(nx, ny, self.css_size(), (ww, wh))
        return self.renderer.window_to_canvas(nx * ww, ny * wh)


SAFE_AREA_JS = """
(function () {
  let d = document.getElementById("lbs-safe");
  if (!d) {
    d = document.createElement("div");
    d.id = "lbs-safe";
    d.style.cssText = "position:fixed;left:0;top:0;width:0;height:0;visibility:hidden;pointer-events:none;" +
      "padding:env(safe-area-inset-top) env(safe-area-inset-right) " +
      "env(safe-area-inset-bottom) env(safe-area-inset-left)";
    document.body.appendChild(d);
  }
  const s = getComputedStyle(d);
  const pads = [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft];
  window.lbsSafe = pads.map((v) => parseFloat(v) || 0).join(",");
})();
"""


def contain_point(nx: float, ny: float, element: tuple[int, int], buffer: tuple[int, int]) -> tuple[float, float]:
    """Undo CSS `object-fit: contain`: SDL reports positions relative to the whole canvas element,
    but the picture is letterboxed inside it whenever the element and the drawing buffer differ in shape."""
    (cw, ch), (bw, bh) = element, buffer
    if cw <= 0 or ch <= 0 or bw <= 0 or bh <= 0:
        return nx, ny
    s = min(cw / bw, ch / bh)
    return (nx * cw - (cw - bw * s) / 2) / (bw * s), (ny * ch - (ch - bh * s) / 2) / (bh * s)


async def run(
    seed: int | None = None,
    max_frames: int | None = None,
    store: ProfileStore | None = None,
    autostart: bool = False,
) -> World:
    """Open the window and play. `max_frames` stops after that many frames (smoke tests)."""
    content = load_content()
    pygame.init()
    pygame.display.set_caption("Last Bean Standing")
    renderer = Renderer(content)
    game = Game(content, renderer, store or default_store(), seed, autostart)
    screen = Screen(renderer, game.profile["settings"]["zoom"])
    effects = Effects(*effect_palette(renderer))
    effects.item_info = {i.id: (i.name, i.text) for i in content.items}
    effects.item_rarity = {i.id: i.rarity for i in content.items}
    effects.taglines = {st.index: st.tagline for st in content.stages}
    effects.boss_phases = {b.id: [str(ph.get("pattern", "")) for ph in b.phases] for b in content.bosses}
    audio = Audio()
    audio.bed_tracks = {st.index: st.biome for st in content.stages}
    touch = TouchState()

    def zoom(steps: int) -> None:
        if screen.change_zoom(steps):
            game.profile["settings"]["zoom"] = screen.zoom
            game.save()

    if game.state == "name":
        game.start_name_entry()
    game.start_sync()  # runs queued while offline
    renderer.set_arena(game.config)
    clock = pygame.time.Clock()
    timer, show_timings, bench_result = FrameTimer(), False, ""
    acc, frames, running, choice = 0.0, 0, True, None
    buttons: list[screens.Button] = []
    touch_ability = False
    offer_action: PlayerInput | None = None
    was_paused = False
    touch_debug = "" if screen.debug_requested() else None
    last = time.perf_counter()
    prev_positions = None
    next_fit = 0.0

    def apply_settings() -> None:
        s = game.profile["settings"]
        audio.volume = s["volume"] / 100
        effects.show_numbers, effects.shake_on = s["numbers"], s["shake"]
        renderer.hud_full = s.get("hud_full", False)

    def toggle_hud() -> None:
        renderer.hud_full = game.profile["settings"]["hud_full"] = not renderer.hud_full
        game.save()

    apply_settings()

    def new_run() -> None:
        nonlocal acc, prev_positions
        game.new_run()
        effects.reset()
        if not game.profile.get("hints_seen"):  # first run: a few tips, one after another
            effects.hints = first_run_hints(renderer.touch)
            game.profile["hints_seen"] = True
            game.save()
        touch.reset()
        acc, prev_positions = 0.0, None

    def do(action: str | None) -> None:
        """Button actions, shared by touch, mouse and keyboard."""
        nonlocal running, acc
        if action is None:
            return
        if action == "play":
            game.state = "characters"  # pick a bean first
        elif action == "again":
            new_run()
        elif action.startswith("char:"):
            game.choose_character(action[5:])
            new_run()
        elif action == "board":
            game.open_board()
        elif action == "name":
            game.start_name_entry()  # touch: on-screen keyboard; otherwise just type
        elif action == "type":
            if not renderer.touch:
                game.type_name()  # browser text dialog as a fallback (e.g. no keyboard focus)
        elif action.startswith("key:"):
            game.press_key(action[4:])
        elif action == "ok":
            game.confirm_name()
        elif action == "prologue_done":
            game.profile["prologue_seen"] = True
            game.save()
            if game.profile.get("nickname"):
                game.state = "menu"
            else:
                game.start_name_entry()
        elif action == "cancel" and game.text_target != "nickname":
            game.state, game.text_target = "account", "nickname"
            pygame.key.stop_text_input()
        elif action in ("cancel", "menu", "back"):
            game.state = "menu"
            pygame.key.stop_text_input()
        elif action == "account":
            game.open_account()
        elif action == "poke":  # tap the bean on the menu: it hops and says something
            game.poke_ms = pygame.time.get_ticks()
        elif action == "squish":  # the menu slug (a challenge counts them)
            game.squish_ms = pygame.time.get_ticks()
            life = game.profile.setdefault("lifetime", {})
            life["menu_squished"] = life.get("menu_squished", 0) + 1
            for ch in challenges.evaluate_profile(game.profile, content.challenges, game.starters):
                effects.toast = (f"Challenge geschafft: {ch.text}", 200)
            game.save()
        elif action.startswith("acc_field:"):
            game.start_text_entry(action.split(":", 1)[1])
        elif action.startswith("acc_"):
            game.account_action(action)
        elif action == "resume":
            game.state, acc = "play", 0.0
        elif action == "mute":
            audio.muted = not audio.muted
        elif action == "challenges":
            game.state, game.challenge_page = "challenges", 0
        elif action.startswith("page:"):
            game.challenge_page = max(0, game.challenge_page + int(action[5:]))
        elif action == "mode":
            game.toggle_mode()
        elif action == "board_mode":
            game.board["mode"] = "eternal_night" if game.board["mode"] == "normal" else "normal"
            game.board["entries"] = None
            game.refresh_board()
        elif action == "skin":
            game.next_skin()
        elif action == "workshop":
            game.state = "workshop"
        elif action == "workshop_back":
            game.apply_workshop()
            game.state = "menu"
        elif action.startswith("gh_tab:"):
            game.workshop_tab = action.split(":", 1)[1]
        elif action.startswith(("gh_buy:", "gh_sell:")):
            verb, kind, item_id = action.split(":", 2)
            if verb == "gh_buy":
                workshop.buy_greenhouse(game.profile, content.shop, kind, item_id)
            else:
                workshop.sell_greenhouse(game.profile, content.shop, kind, item_id)
            game.save()
        elif action.startswith(("pack_buy:", "pack_back:")):
            kind, pid = action.split(":", 1)
            if kind == "pack_buy":
                workshop.buy_pack(game.profile, content.shop, pid)
            else:
                workshop.return_pack(game.profile, content.shop, pid)
            game.save()
        elif action.startswith(("ws_buy:", "ws_sell:")):
            game.workshop_action(*action.split(":", 1))
        elif action == "settings":
            game.settings_return = game.state
            game.state = "settings"
        elif action == "settings_back":
            game.state = game.settings_return
        elif action == "set:zoom":  # cycle: closer and closer ... then all the way out again
            if not screen.change_zoom(-1):
                while screen.change_zoom(1):
                    pass
            game.profile["settings"]["zoom"] = screen.zoom
            game.save()
        elif action.startswith("set:"):
            game.change_setting(action[4:])
            apply_settings()
        elif action == "quit":
            running = False
        elif action.startswith("period:"):
            game.board["period"], game.board["entries"] = action.split(":", 1)[1], None
            game.refresh_board()

    def card_action(action: str) -> None:
        nonlocal offer_action
        if action == "reroll":
            offer_action, renderer.banish_mode = PlayerInput(0, reroll=True), False
        elif action == "banish":
            renderer.banish_mode = not renderer.banish_mode
        elif action in ("gate_yes", "gate_no"):
            offer_action = PlayerInput(0, gate=action == "gate_yes")

    def pick_card(i: int) -> None:
        """A card tap or 1/2/3: take it, or banish it while banish mode is on."""
        nonlocal choice, offer_action
        if renderer.banish_mode:
            offer_action, renderer.banish_mode = PlayerInput(0, banish=i), False
        else:
            choice = i

    def tap(pos: tuple[int, int]) -> None:
        nonlocal choice, touch_ability
        if game.state == "play":
            if game.world.paused:
                for rect, action in renderer.offer_buttons:
                    if rect.collidepoint(pos):
                        card_action(action)
                        return
                for i, rect in enumerate(renderer.card_rects):
                    if rect.collidepoint(pos):
                        pick_card(i)
            elif renderer.pause_rect.collidepoint(pos):
                game.state = "pause"
            elif renderer.hud_rect.collidepoint(pos):
                toggle_hud()
            elif renderer.ability_rect.collidepoint(pos):
                touch_ability = True
        else:
            do(screens.hit(buttons, pos))

    try:
        while running:
            if WEB and time.monotonic() >= next_fit:  # page resized or device rotated
                screen.fit()
                next_fit = time.monotonic() + 0.5
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif (
                    game.state == "play"
                    and effects.reel is not None
                    and event.type in (pygame.FINGERDOWN, pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN)
                ):
                    effects.skip_reel()  # chest draw: a tap or key skips the spin, a second one closes it
                elif event.type == pygame.WINDOWFOCUSLOST and game.state == "play" and not game.world.paused:
                    game.state = "pause"  # switching tabs or apps must not cost the run
                    touch.reset()
                elif event.type == pygame.VIDEORESIZE and not WEB:
                    screen.fit()
                elif event.type == pygame.FINGERDOWN:
                    renderer.touch = True
                    pos = screen.to_canvas(event)
                    if touch_debug is not None:
                        ww, wh = screen.window.get_size()
                        touch_debug = (
                            f"tap {event.x:.2f},{event.y:.2f} -> {pos} {game.state}\n"
                            f"canvas {renderer.w}x{renderer.h} win {ww}x{wh} css {screen._css[0]}x{screen._css[1]}"
                        )
                    on_button = any(r.collidepoint(pos) for r in (renderer.ability_rect, renderer.pause_rect,
                                                                       renderer.hud_rect))  # fmt: skip
                    steer = game.state == "play" and not game.world.paused and not on_button
                    touch.down(event.finger_id, *pos, steer=steer, button=on_button and game.state == "play")
                    if game.state == "play" and not game.world.paused and on_button:
                        tap(pos)  # buttons react on touch down, so a running thumb is never blocked
                elif event.type == pygame.FINGERMOTION:
                    touch.move(event.finger_id, *screen.to_canvas(event))
                elif event.type == pygame.MOUSEWHEEL:
                    zoom(-1 if event.y > 0 else 1)
                elif event.type == pygame.FINGERUP:
                    pos = screen.to_canvas(event)
                    in_game = game.state == "play" and not game.world.paused
                    if touch.up(event.finger_id, *pos) and not in_game:
                        tap(pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not getattr(event, "touch", False):
                    tap(screen.to_canvas(event))
                elif game.state == "name":
                    game.handle_name_event(event)
                elif game.state == "prologue" and event.type == pygame.KEYDOWN:
                    do("prologue_done")
                elif event.type != pygame.KEYDOWN:
                    continue
                elif event.key == pygame.K_m:
                    audio.muted = not audio.muted
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    zoom(-1)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    zoom(1)
                elif event.key == pygame.K_F11 and not WEB:
                    pygame.display.toggle_fullscreen()
                elif event.key == pygame.K_F3:
                    show_timings = not show_timings
                elif event.key == pygame.K_F5:
                    bench_result = benchmark(content, renderer)
                    print(bench_result)
                    show_timings, last = True, time.perf_counter()
                elif game.state == "menu":
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        do("play")
                    elif event.key == pygame.K_n:
                        game.start_name_entry()
                    elif event.key == pygame.K_l:
                        do("board")
                    elif event.key == pygame.K_ESCAPE and not WEB:
                        running = False
                elif game.state == "characters":
                    ids = [c.id for c in game.characters]
                    if pygame.K_1 <= event.key <= pygame.K_9 and event.key - pygame.K_1 < len(ids):
                        do(f"char:{ids[event.key - pygame.K_1]}")
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        do(f"char:{game.character}")
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        step = 1 if event.key == pygame.K_RIGHT else -1
                        game.character = ids[(ids.index(game.character) + step) % len(ids)]
                    elif event.key == pygame.K_ESCAPE:
                        do("menu")
                elif game.state == "board":
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        game.switch_period(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        game.switch_period(1)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        do("back")
                elif game.state == "results":
                    if event.key == pygame.K_r:
                        do("again")
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                        do("menu")
                elif game.state == "settings":
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        do("settings_back")
                elif game.state == "workshop":
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        do("workshop_back")
                elif game.state == "challenges":
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        do("menu")
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        do("page:1" if event.key == pygame.K_RIGHT else "page:-1")
                elif game.state == "pause":
                    if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_p):
                        do("resume")
                    elif event.key == pygame.K_r:
                        do("again")
                    elif event.key == pygame.K_q:
                        do("menu")  # abandon the run, it is not recorded
                elif event.key in (pygame.K_ESCAPE, pygame.K_p) and not game.world.paused:
                    game.state = "pause"
                elif event.key == pygame.K_TAB and game.state == "play":
                    toggle_hud()
                elif event.key == pygame.K_F4:
                    game.config = game.normal if game.config is not game.normal else stress_config(game.normal)
                    new_run()
                elif game.world.paused and game.world.players[0].gate_prompt:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_y, pygame.K_j):
                        card_action("gate_yes")
                    elif event.key in (pygame.K_ESCAPE, pygame.K_n, pygame.K_BACKSPACE):
                        card_action("gate_no")
                elif game.world.paused:
                    if event.key == pygame.K_r:
                        card_action("reroll")
                    elif event.key == pygame.K_b:
                        card_action("banish")
                    else:
                        picked = card_choice(event.key, renderer)
                        if picked is not None:
                            pick_card(picked)
            # Web: the browser paces frames (requestAnimationFrame), an extra 60 fps cap would drop frames.
            acc += min((clock.tick() if WEB else clock.tick(120)) / 1000.0, DT * MAX_STEPS_PER_FRAME)
            t0 = time.perf_counter()
            world = game.world
            frame_events: list = []
            if game.state == "play":
                if world.paused:
                    acc = 0.0
                    if not was_paused:  # cards just opened: forget fingers that were steering, keep new taps
                        touch.reset()
                    if offer_action is not None:
                        frame_events += world.step([offer_action])
                    elif choice is not None:
                        frame_events += world.step([PlayerInput(0, choice=choice)])
                        renderer.selected = 0
                    elif game.config is not game.normal:
                        frame_events += world.step([PlayerInput(0, choice=0, gate=True)])  # stress test: automatic
                elif effects.reel is not None or effects.intro is not None:  # chest draw or boss entrance
                    acc = 0.0
                elif effects.hitstop > 0:  # hit-stop: the picture holds for a few frames, the run just waits
                    effects.hitstop -= 1
                    acc = 0.0
                else:
                    inputs = [combine_input(read_input(0), touch.direction(), touch_ability)]
                    while acc >= DT and not world.paused and not world.over:
                        if acc < 2 * DT:  # last step of this frame: remember where everything was
                            prev_positions = world.positions()
                        frame_events += world.step(inputs)
                        acc -= DT
                        inputs = [dataclasses.replace(inputs[0], ability=False)]  # one press, one use
                    touch_ability = False
                if frame_events:
                    positions = {p.player_id: (p.x, p.y) for p in world.players}
                    effects.handle(frame_events, renderer.boss_names, positions)
                audio.handle(frame_events)
                effects.update()
                if world.over:
                    game.finish_run()
                    touch.reset()
            else:
                acc = 0.0
                if game.state != "pause" and not (game.state == "settings" and game.settings_return == "pause"):
                    audio.music(None)  # menus are quiet; the next run starts its bed's track
            choice, offer_action = None, None
            was_paused = game.state == "play" and game.world.paused
            t1 = time.perf_counter()
            buttons = []
            if game.state in ("play", "results", "pause"):
                debug = f"{timer.text(world)}  {bench_result}" if show_timings else None
                snap = world.snapshot()
                if game.state == "play" and not world.paused and effects.hitstop <= 0:
                    snap = interpolate(snap, prev_positions, acc / DT)  # smooth motion between ticks
                renderer.draw(snap, debug=debug, effects=effects)
                if game.state == "play" and touch.stick is not None:
                    renderer.draw_stick(touch.stick)
                if game.state == "pause":
                    buttons = screens.draw_pause(renderer, game.world.snapshot(), audio.muted)
                if game.state == "results":
                    line = screens.online_line(*game.online)
                    buttons = screens.draw_results(renderer, game.result, game.flags, game.profile, line)
            elif game.state == "menu":
                buttons = screens.draw_menu(renderer, game.profile, WEB, game.character, game.poke_ms,
                                            renderer.character_tint, game.squish_ms)  # fmt: skip
                if effects.toast:  # e.g. a challenge done right here in the menu
                    renderer.text(effects.toast[0], (renderer.w // 2, renderer.h - 30), center=True)
                    effects.update()
            elif game.state == "characters":
                best = game.profile["highscores"].get("by_character", {})
                choices = game.skin_choices()
                skins = {c.id: tuple(s.tint) for c in game.characters for s in content.skins
                         if s.id == game.profile.get("skin", {}).get(c.id)}  # fmt: skip
                label = ""
                if len(choices) > 1:
                    current = next((s for s in choices if s and s.id == game.profile["skin"].get(game.character)), None)
                    who = next(c.name for c in game.characters if c.id == game.character)
                    label = f"{who}: {current.name if current else 'normal'}"
                mode_label = ""
                if "eternal_night" in game.profile["unlocked"]["modes"]:
                    mode_label = "Ewige Nacht" if game.mode == "eternal_night" else "Modus: normal"
                open_ids = {c.id for c in game.characters}
                locked = {c.id: next((h.text for h in content.challenges if h.id == c.unlock_challenge), "")
                          for c in game.all_characters if c.id not in open_ids}  # fmt: skip
                buttons = screens.draw_characters(renderer, game.all_characters, game.character, best, skins, label,
                                                  mode_label, locked)  # fmt: skip
            elif game.state == "prologue":
                buttons = screens.draw_prologue(renderer)
            elif game.state == "settings":
                label = zoom_label(min(renderer.w, renderer.h), screen.default_short())
                buttons = screens.draw_settings(renderer, game.profile["settings"], label)
            elif game.state == "workshop":
                buttons = screens.draw_greenhouse(renderer, content, game.profile, game.workshop_tab)
            elif game.state == "challenges":
                buttons = screens.draw_challenges(renderer, content, game.profile, game.challenge_page,
                                                  game.starters)  # fmt: skip
            elif game.state == "board":
                if time.monotonic() - game.board["fetched_at"] > REFRESH_S:
                    game.refresh_board()
                buttons = screens.draw_board(renderer, game.board, game.profile, game.leaderboard.enabled)
            else:
                if game.text_target == "nickname":
                    valid = valid_nickname(game.name_buffer)
                    buttons = screens.draw_name_entry(
                        renderer, game.name_buffer, valid, game.first_name, keyboard=renderer.touch,
                        upper=game.name_upper,
                    )  # fmt: skip
                else:
                    password = game.text_target == "acc_pw"
                    valid = len(game.name_buffer) >= 6 if password else valid_nickname(game.name_buffer)
                    buttons = screens.draw_name_entry(
                        renderer, game.name_buffer, valid, False, keyboard=renderer.touch, upper=game.name_upper,
                        title="Passwort" if password else "Kontoname", mask=password,
                    )  # fmt: skip
            if game.state == "account":
                buttons = screens.draw_account(renderer, game.profile, game.acc_form, game.acc_status,
                                               game.acc_config, game.account.enabled, WEB)  # fmt: skip
            game.passkey_zones(buttons, screen)
            if touch_debug is not None:
                for i, line in enumerate((touch_debug or "Tippe irgendwo hin").split("\n")):
                    renderer.text(line, (4, renderer.h - 34 + i * 14))
                for b in buttons:
                    pygame.draw.rect(renderer.canvas, (255, 60, 60), b.rect, 1)
            renderer.present(screen.window)
            pygame.display.flip()
            t2 = time.perf_counter()
            timer.add(sim=t1 - t0, draw=t2 - t1, frame=t2 - last)
            last = t2
            frames += 1
            if max_frames is not None and frames >= max_frames:
                running = False
            await asyncio.sleep(0)
    finally:
        pygame.quit()
    return game.world


EPITAPHS = (
    "Hier ruht {bean}. {n}× {pest} hat es erwischt, eine hat zurückgebissen.",
    "{bean} ist jetzt Dünger. Die {pest} jubeln ({n} von ihnen nicht mehr).",
    "Ruhe sanft, {bean}. Du hast {n}× {pest} gezeigt, wo der Spaten hängt.",
    "{bean} wurde zu Kompost. Immerhin {n}× {pest} gingen mit.",
)


def epitaph(result: dict, content, nickname: str | None) -> str:
    """A gravestone line with a wink for a lost run: the pest the bean beat most often."""
    if result.get("victory"):
        return "Der Schnitter hat seine Ernte verloren."
    kinds = {k[5:]: v for k, v in (result.get("stats") or {}).items() if k.startswith("kind_")}
    if not kinds:
        return ""
    top = max(kinds, key=lambda k: (kinds[k], k))
    pest = next((m.name for m in content.mobs if m.id == top), top)
    bean = next((c.name for c in content.characters if c.id == result.get("character")), nickname or "Bohne")
    line = EPITAPHS[int(result.get("seed", 0)) % len(EPITAPHS)]
    return line.format(bean=bean, n=int(kinds[top]), pest=pest)


def first_run_hints(touch: bool) -> list[str]:
    """Tips for the very first run (and again on request in the settings)."""
    move = "Zieh mit dem Daumen, um zu laufen." if touch else "Laufen mit WASD oder den Pfeiltasten."
    ability = "Der Knopf unten rechts löst deine Fähigkeit aus." if touch else "Leertaste: deine Fähigkeit."
    return [
        f"{move} Deine Bohne schießt von selbst.",
        "Sammle die Funken der Plagen: Jedes Level bringt eine neue Karte.",
        ability,
        "Schreine: Bleib im Kreis stehen. Mehr Belohnung, aber die Plagen werden stärker.",
        "Bei 2:06 kommt der Boss. Besiegt öffnet er das Gartentor; lauf hinein, wenn du bereit bist.",
    ]


def zoom_label(short: int, default: int) -> str:
    """How close the camera is compared to the device's normal view (shorter side in canvas pixels)."""
    ratio = short / max(1, default)
    return "sehr nah" if ratio < 0.85 else "nah" if ratio < 0.96 else "normal" if ratio <= 1.08 else \
        "weit" if ratio < 1.4 else "sehr weit"  # fmt: skip


def combine_input(keys: PlayerInput, stick: tuple[int, int], touch_ability: bool) -> PlayerInput:
    """Keyboard and touch together: the stick wins when it is deflected."""
    mx, my = stick if stick != (0, 0) else (keys.move_x, keys.move_y)
    return PlayerInput(keys.player_id, mx, my, ability=keys.ability or touch_ability)
