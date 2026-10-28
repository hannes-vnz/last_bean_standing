"""Optional account with cloud save (Paket K): the same server as the leaderboard (`/v1/account/*`, `/v1/save`).

Name + password works everywhere. Google and Apple sign-in run in the browser build once the server reports
their client ids (`/v1/config`); the provider's ID token goes to the server, which checks it. The game keeps
working offline; the session token lives in the profile (`profile["account"]`).
"""

from __future__ import annotations

import json
from typing import Any

from . import http
from .leaderboard import Requester, server_url


class Account:
    def __init__(self, base_url: str | None = None, requester: Requester | None = None) -> None:
        self.base_url = (server_url() if base_url is None else base_url).rstrip("/")
        self.request = requester or http.request

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @staticmethod
    def _error(status: int, data: Any) -> str:
        if status == 0:
            return "Server nicht erreichbar"
        if isinstance(data, dict) and data.get("detail"):
            detail = data["detail"]
            return detail if isinstance(detail, str) else "Eingabe ungültig"
        return f"Server meldet {status}"

    async def config(self) -> dict:
        status, data = await self.request("GET", self.base_url + "/v1/config")
        return data if status == 200 and isinstance(data, dict) else {}

    async def sign_in(self, kind: str, body: dict) -> tuple[dict | None, str]:
        """kind: "register", "login" or "oauth". Returns ({name, session}, "") or (None, error)."""
        status, data = await self.request("POST", f"{self.base_url}/v1/account/{kind}", body)
        if status == 200 and isinstance(data, dict) and data.get("session"):
            return data, ""
        return None, self._error(status, data)

    async def load(self, session: str) -> tuple[int, dict | None]:
        status, data = await self.request("GET", self.base_url + "/v1/save", None, _auth(session))
        profile = data.get("profile") if status == 200 and isinstance(data, dict) else None
        return status, profile if isinstance(profile, dict) else None

    async def store(self, session: str, profile: dict) -> int:
        status, _ = await self.request("PUT", self.base_url + "/v1/save", {"profile": cloud_copy(profile)},
                                       _auth(session))  # fmt: skip
        return status

    async def sign_out(self, session: str) -> None:
        await self.request("POST", self.base_url + "/v1/account/logout", None, _auth(session))


def _auth(session: str) -> dict:
    return {"Authorization": "Bearer " + session}


def cloud_copy(profile: dict) -> dict:
    """The profile as stored in the cloud: without the session itself and the local settings."""
    data = json.loads(json.dumps(profile))
    data.pop("account", None)
    data.pop("settings", None)
    return data


def merge(local: dict, cloud: dict) -> dict:
    """Combine this device's profile with the cloud save: the one with more runs leads, and nothing that was
    earned on either side is lost (challenges, titles, skins, unlocks, workshop levels)."""
    runs = lambda p: (p.get("totals") or {}).get("runs", 0)  # noqa: E731
    if runs(cloud) >= runs(local):
        base, other = json.loads(json.dumps(cloud)), local
    else:
        base, other = json.loads(json.dumps(local)), cloud
    for key in ("challenges_done", "titles", "skins"):
        base[key] = list(dict.fromkeys([*(base.get(key) or []), *(other.get(key) or [])]))
    unlocked = base.setdefault("unlocked", {})
    for key, ids in (other.get("unlocked") or {}).items():
        unlocked[key] = list(dict.fromkeys([*(unlocked.get(key) or []), *ids]))
    shop = base.setdefault("workshop", {})
    for wid, level in (other.get("workshop") or {}).items():
        shop[wid] = max(shop.get(wid, 0), level)
    for key in ("settings", "account"):  # stay as they are on this device
        if key in local:
            base[key] = local[key]
    return base


# ---------------------------------------------------------------------------- browser: Google and Apple sign-in

_JS_SIGN_IN = """
window.lbsIdToken = window.lbsIdToken || "";
window.lbsTakeIdToken = function () { const t = window.lbsIdToken; window.lbsIdToken = ""; return t; };
window.lbsLoadScript = function (src, then) {
  if (document.querySelector('script[src="' + src + '"]')) { then(); return; }
  const s = document.createElement("script"); s.src = src; s.onload = then; document.head.appendChild(s);
};
window.lbsSignIn = function (provider, clientId) {
  window.lbsIdToken = "";
  if (provider === "google") {
    window.lbsLoadScript("https://accounts.google.com/gsi/client", function () {
      let box = document.getElementById("lbs-signin");
      if (!box) {
        box = document.createElement("div"); box.id = "lbs-signin";
        box.style.cssText = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9999;" +
          "background:#fff8e7;border:3px solid #4a3358;padding:16px;border-radius:8px;text-align:center";
        document.body.appendChild(box);
      }
      box.innerHTML = '<div id="lbs-gbtn"></div><div style="margin-top:10px;cursor:pointer;font:14px sans-serif" ' +
        'onclick="document.getElementById(\\'lbs-signin\\').remove(); window.lbsIdToken=\\'cancel\\'">Abbrechen</div>';
      google.accounts.id.initialize({client_id: clientId, callback: function (r) {
        window.lbsIdToken = r.credential || "cancel";
        const b = document.getElementById("lbs-signin"); if (b) b.remove();
      }});
      google.accounts.id.renderButton(document.getElementById("lbs-gbtn"), {theme: "outline", size: "large"});
    });
  } else if (provider === "apple") {
    const apple = "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/de_DE/appleid.auth.js";
    window.lbsLoadScript(apple, function () {
      const back = location.origin + location.pathname;
      AppleID.auth.init({clientId: clientId, scope: "", redirectURI: back, usePopup: true});
      AppleID.auth.signIn()
        .then(function (r) { window.lbsIdToken = (r.authorization && r.authorization.id_token) || "cancel"; })
        .catch(function () { window.lbsIdToken = "cancel"; });
    });
  }
};
"""
_sign_in_installed = False


async def browser_id_token(provider: str, client_id: str, timeout_s: float = 180.0) -> str:
    """Show the provider's sign-in in the page and wait for its ID token ("" when cancelled or not in a browser)."""
    import asyncio

    try:
        import platform  # pygbag's bridge to the page

        window = platform.window
    except (ImportError, AttributeError):
        return ""
    global _sign_in_installed
    if not _sign_in_installed:
        window.eval(_JS_SIGN_IN)
        _sign_in_installed = True
    window.lbsSignIn(provider, client_id)
    waited = 0.0
    while waited < timeout_s:
        token = str(window.lbsTakeIdToken() or "")
        if token:
            return "" if token == "cancel" else token
        await asyncio.sleep(0.1)
        waited += 0.1
    return ""
