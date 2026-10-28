// Last Bean Standing leaderboard on Cloudflare Workers + D1.
// Port of server/app.py (the Python reference): same routes, same JSON, same checks (stage 1).
// Players have a nickname and a random token that stays on their device; only its SHA-256 hash is stored.
//
// Bindings (wrangler.toml): DB (D1). Vars: ALLOWED_ORIGINS, ALLOWED_VERSIONS, RATE_LIMIT_PER_MIN.
// Secret: ADMIN_TOKEN (wrangler secret put ADMIN_TOKEN) for moderation.
// Accounts (Paket K, optional): name + password (PBKDF2), or Google / Apple sign-in when the vars
// GOOGLE_CLIENT_ID / APPLE_CLIENT_ID are set (their ID tokens are checked against the providers' public keys).
// A signed-in player keeps the profile in the cloud: GET/PUT /v1/save.

const CHARACTERS = new Set(["ranger", "pyro", "rogue", "guardian", "cryo", "summoner", "storm", "bomber", "venom", "sniper"]);
const MODES = new Set(["normal", "eternal_night"]);
const MODE_SCORE_MULT = { normal: 1.0, eternal_night: 1.5 }; // data/modes.json score_mult
const FLOOD_START_S = 180; // the flood begins when the first garden bed (3:00, data/stages.json) runs out
const NAME_RE = /^[A-Za-z0-9ÄÖÜäöüß _\-.]{2,16}$/;
const RUN_ID_RE = /^[A-Za-z0-9-]+$/;
const PERIOD_SECONDS = { day: 86400, week: 7 * 86400, month: 30 * 86400 };

class HttpError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

// ----------------------------------------------------------------------------- validation (pydantic ScoreIn)

function int(v, name, lo, hi) {
  if (!Number.isInteger(v) || v < lo || v > hi) throw new HttpError(422, `${name}: ganze Zahl von ${lo} bis ${hi}`);
  return v;
}

function str(v, name, lo, hi) {
  if (typeof v !== "string" || v.length < lo || v.length > hi) throw new HttpError(422, `${name}: Text mit ${lo} bis ${hi} Zeichen`);
  return v;
}

export function parseScore(b) {
  if (!b || typeof b !== "object" || Array.isArray(b)) throw new HttpError(422, "JSON-Objekt erwartet");
  const s = {
    run_id: str(b.run_id, "run_id", 8, 64),
    client_token: str(b.client_token, "client_token", 16, 128),
    name: typeof b.name === "string" ? b.name.trim() : "",
    character: b.character,
    mode: b.mode === undefined ? "normal" : b.mode,
    score: int(b.score, "score", 0, 100_000_000),
    seconds: int(b.seconds, "seconds", 1, 7200),
    wave: int(b.wave, "wave", 1, 300),
    kills: int(b.kills, "kills", 0, 200_000),
    level: int(b.level, "level", 1, 200),
    bosses: int(b.bosses, "bosses", 0, 20),
    difficulty: b.difficulty,
    swarm_seconds: b.swarm_seconds === undefined ? 0 : int(b.swarm_seconds, "swarm_seconds", 0, 7200),
    victory: b.victory === undefined ? false : b.victory,
    version: str(b.version, "version", 1, 20),
    seed: b.seed === undefined || b.seed === null ? null : int(b.seed, "seed", -(2 ** 53), 2 ** 53),
    replay: b.replay === undefined || b.replay === null ? null : str(b.replay, "replay", 0, 200_000),
  };
  if (!RUN_ID_RE.test(s.run_id)) throw new HttpError(422, "run_id: nur Buchstaben, Ziffern und -");
  if (!NAME_RE.test(s.name)) throw new HttpError(422, "Name: 2 bis 16 Zeichen (Buchstaben, Ziffern, Leerzeichen, _ - .)");
  if (!CHARACTERS.has(s.character)) throw new HttpError(422, "unbekannter Charakter");
  if (!MODES.has(s.mode)) throw new HttpError(422, "unbekannter Modus");
  if (typeof s.difficulty !== "number" || !(s.difficulty >= 1 && s.difficulty <= 10)) throw new HttpError(422, "difficulty: 1 bis 10");
  if (typeof s.victory !== "boolean") throw new HttpError(422, "victory: true oder false");
  return s;
}

// Upper bound from the score formula in docs/CONTENT.md (time, kills, level, bosses, victory, swarm, difficulty).
export function maxPlausibleScore(s) {
  let base = 2 * s.seconds + 5 * s.kills + 20 * s.level + 500 * s.bosses;
  base += s.victory ? 20000 : 0;
  base += 1000 * (s.swarm_seconds / 10) * 8;
  return base * (1 + 0.8 * (s.difficulty - 1)) * (MODE_SCORE_MULT[s.mode] ?? 1.0) * 1.02 + 50;
}

export function plausibilityError(s, env) {
  if (s.score > maxPlausibleScore(s)) return "Punkte passen nicht zu Zeit, Kills und Level";
  if (s.kills > s.seconds * 40) return "zu viele Kills fuer die Spielzeit";
  if (Math.abs(s.wave - (Math.floor(s.seconds / 30) + 1)) > 2 && s.swarm_seconds === 0) return "Welle passt nicht zur Spielzeit";
  if (s.swarm_seconds > Math.max(0, s.seconds - FLOOD_START_S + 5)) return "Flutzeit passt nicht zur Spielzeit";
  if (s.bosses > 6 + Math.floor(s.seconds / 900)) return "zu viele Bosse";
  const allowed = (env.ALLOWED_VERSIONS || "").split(",").filter(Boolean);
  if (allowed.length && !allowed.includes(s.version)) return "Spielversion wird nicht mehr angenommen";
  return null;
}

// ----------------------------------------------------------------------------- helpers

async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sameText(a, b) {
  // constant-time comparison for hashes and tokens
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// Best effort per isolate: Workers run in several isolates, so this caps bursts, not a global rate.
const hits = new Map();
function rateLimited(key, limit, windowS = 60) {
  const now = Date.now() / 1000;
  const q = (hits.get(key) || []).filter((t) => now - t <= windowS);
  if (q.length >= limit) {
    hits.set(key, q);
    return true;
  }
  q.push(now);
  hits.set(key, q);
  if (hits.size > 10_000) hits.clear();
  return false;
}

async function rank(db, score, seconds, mode, character) {
  let q = "SELECT COUNT(*) AS n FROM scores WHERE mode=? AND (score>? OR (score=? AND seconds<?))";
  const args = [mode, score, score, seconds];
  if (character) {
    q += " AND character=?";
    args.push(character);
  }
  const row = await db.prepare(q).bind(...args).first();
  return row.n + 1;
}

function corsHeaders(request, env) {
  const allowed = (env.ALLOWED_ORIGINS || "*").split(",").map((s) => s.trim());
  const origin = request.headers.get("Origin");
  const allow = allowed.includes("*") ? "*" : allowed.includes(origin) ? origin : allowed[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Client-Token, X-Admin-Token",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(data, status, cors) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json", ...cors } });
}

// ----------------------------------------------------------------------------- routes

async function submit(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "?";
  if (rateLimited("ip:" + ip, parseInt(env.RATE_LIMIT_PER_MIN || "10", 10))) throw new HttpError(429, "zu viele Anfragen");
  let body;
  try {
    body = await request.json();
  } catch {
    throw new HttpError(422, "ungueltiges JSON");
  }
  const s = parseScore(body);
  const err = plausibilityError(s, env);
  if (err) throw new HttpError(422, err);
  const owner = await sha256(s.client_token);
  let row = await env.DB.prepare("SELECT * FROM scores WHERE run_id=?").bind(s.run_id).first();
  if (!row) {
    await env.DB.prepare(
      `INSERT INTO scores (run_id, owner_hash, name, character, mode, score, seconds, wave, kills, level, bosses,
       difficulty, swarm_seconds, victory, version, seed, replay, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
       ON CONFLICT(run_id) DO NOTHING`,
    )
      .bind(s.run_id, owner, s.name, s.character, s.mode, s.score, s.seconds, s.wave, s.kills, s.level, s.bosses,
            s.difficulty, s.swarm_seconds, s.victory ? 1 : 0, s.version, s.seed, s.replay, Math.floor(Date.now() / 1000))
      .run();
    row = await env.DB.prepare("SELECT * FROM scores WHERE run_id=?").bind(s.run_id).first();
  }
  if (!sameText(row.owner_hash, owner)) throw new HttpError(409, "run_id gehoert einem anderen Spieler");
  return {
    id: row.id,
    rank_overall: await rank(env.DB, row.score, row.seconds, row.mode, null),
    rank_character: await rank(env.DB, row.score, row.seconds, row.mode, row.character),
  };
}

async function leaderboard(url, env) {
  const p = url.searchParams;
  const mode = p.get("mode") || "normal";
  const character = p.get("character");
  const period = p.get("period") || "all";
  const limit = p.has("limit") ? Number(p.get("limit")) : 50;
  const offset = p.has("offset") ? Number(p.get("offset")) : 0;
  if (!MODES.has(mode)) throw new HttpError(422, "unbekannter Modus");
  if (character !== null && !CHARACTERS.has(character)) throw new HttpError(422, "unbekannter Charakter");
  if (period !== "all" && !(period in PERIOD_SECONDS)) throw new HttpError(422, "unbekannter Zeitraum");
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new HttpError(422, "limit: 1 bis 100");
  if (!Number.isInteger(offset) || offset < 0 || offset > 10_000) throw new HttpError(422, "offset: 0 bis 10000");
  let q = "SELECT * FROM scores WHERE mode=?";
  const args = [mode];
  if (character) {
    q += " AND character=?";
    args.push(character);
  }
  if (period !== "all") {
    q += " AND created_at>=?";
    args.push(Math.floor(Date.now() / 1000) - PERIOD_SECONDS[period]);
  }
  q += " ORDER BY score DESC, seconds ASC, id ASC LIMIT ? OFFSET ?";
  args.push(limit, offset);
  const { results } = await env.DB.prepare(q).bind(...args).all();
  const entries = results.map((r, i) => ({
    rank: offset + i + 1, name: r.name, character: r.character, score: r.score, seconds: r.seconds, wave: r.wave,
    kills: r.kills, level: r.level, victory: !!r.victory, swarm_seconds: r.swarm_seconds, difficulty: r.difficulty,
    verified: !!r.verified, created_at: r.created_at,
  }));
  return { mode, character, period, entries };
}

async function deleteMine(request, env) {
  const token = request.headers.get("X-Client-Token");
  if (!token) throw new HttpError(422, "X-Client-Token fehlt");
  const res = await env.DB.prepare("DELETE FROM scores WHERE owner_hash=?").bind(await sha256(token)).run();
  return { deleted: res.meta.changes };
}

async function adminDelete(request, env, id) {
  const expected = env.ADMIN_TOKEN || "";
  if (!expected || !sameText(expected, request.headers.get("X-Admin-Token") || "")) throw new HttpError(403, "kein Zugriff");
  const res = await env.DB.prepare("DELETE FROM scores WHERE id=?").bind(id).run();
  if (!res.meta.changes) throw new HttpError(404, "nicht gefunden");
  return { deleted: res.meta.changes };
}

// ----------------------------------------------------------------------------- accounts and cloud saves

const PBKDF2_ITERATIONS = 100_000; // the most Workers allow; server/app.py uses the same
const SESSION_DAYS = 180;
const MAX_SAVE_CHARS = 200_000;
const OIDC = {
  google: { jwks: "https://www.googleapis.com/oauth2/v3/certs", issuers: ["https://accounts.google.com", "accounts.google.com"], env: "GOOGLE_CLIENT_ID" },
  apple: { jwks: "https://appleid.apple.com/auth/keys", issuers: ["https://appleid.apple.com"], env: "APPLE_CLIENT_ID" },
};

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const unhex = (s) => new Uint8Array(s.match(/../g).map((h) => parseInt(h, 16)));

export async function hashPassword(password, salt) {
  salt = salt || hex(crypto.getRandomValues(new Uint8Array(16)));
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: unhex(salt), iterations: PBKDF2_ITERATIONS }, key, 256);
  return `pbkdf2$${PBKDF2_ITERATIONS}$${salt}$${hex(bits)}`;
}

async function checkPassword(password, stored) {
  const parts = (stored || "").split("$");
  if (parts.length !== 4) return false;
  return sameText(await hashPassword(password, parts[2]), stored);
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    throw new HttpError(422, "ungueltiges JSON");
  }
}

async function newSession(env, accountId) {
  const token = hex(crypto.getRandomValues(new Uint8Array(32)));
  const expires = Math.floor(Date.now() / 1000) + SESSION_DAYS * 86400;
  await env.DB.prepare("INSERT INTO sessions (token_hash, account_id, expires_at) VALUES (?,?,?)").bind(await sha256(token), accountId, expires).run();
  return token;
}

async function accountOf(request, env) {
  const token = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/, "").trim();
  const row = await env.DB.prepare("SELECT account_id, expires_at FROM sessions WHERE token_hash=?").bind(await sha256(token)).first();
  if (!row || row.expires_at < Date.now() / 1000) throw new HttpError(401, "nicht angemeldet");
  return row.account_id;
}

async function credentials(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "?";
  if (rateLimited("auth:" + ip, parseInt(env.RATE_LIMIT_PER_MIN || "10", 10))) throw new HttpError(429, "zu viele Anfragen");
  const b = await readJson(request);
  const name = typeof b.name === "string" ? b.name.trim() : "";
  if (!NAME_RE.test(name)) throw new HttpError(422, "Name: 2 bis 16 Zeichen (Buchstaben, Ziffern, Leerzeichen, _ - .)");
  if (typeof b.password !== "string" || b.password.length < 6 || b.password.length > 128) throw new HttpError(422, "Passwort: 6 bis 128 Zeichen");
  return { name, password: b.password };
}

async function register(request, env) {
  const { name, password } = await credentials(request, env);
  if (await env.DB.prepare("SELECT 1 AS x FROM accounts WHERE name=?").bind(name).first()) throw new HttpError(409, "Name ist schon vergeben");
  const res = await env.DB.prepare("INSERT INTO accounts (name, password, provider, subject, created_at) VALUES (?,?,?,?,?)")
    .bind(name, await hashPassword(password), "password", name.toLowerCase(), Math.floor(Date.now() / 1000)).run();
  return { name, session: await newSession(env, res.meta.last_row_id) };
}

async function login(request, env) {
  const { name, password } = await credentials(request, env);
  const row = await env.DB.prepare("SELECT id, name, password FROM accounts WHERE name=? AND provider='password'").bind(name).first();
  if (!row || !(await checkPassword(password, row.password))) throw new HttpError(401, "Name oder Passwort stimmt nicht");
  return { name: row.name, session: await newSession(env, row.id) };
}

function b64url(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(s + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
}

// Checks an OpenID Connect ID token (RS256) from Google or Apple: signature, issuer, audience, expiry.
async function verifyIdToken(provider, idToken, clientId) {
  const cfg = OIDC[provider];
  const [h, p, sig] = (idToken || "").split(".");
  if (!h || !p || !sig) throw new HttpError(401, "Anmeldung ungültig");
  const header = JSON.parse(new TextDecoder().decode(b64url(h)));
  const claims = JSON.parse(new TextDecoder().decode(b64url(p)));
  const { keys } = await (await fetch(cfg.jwks)).json();
  const jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk || header.alg !== "RS256") throw new HttpError(401, "Anmeldung ungültig");
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64url(sig), new TextEncoder().encode(`${h}.${p}`));
  const now = Date.now() / 1000;
  if (!ok || !cfg.issuers.includes(claims.iss) || claims.aud !== clientId || claims.exp < now || !claims.sub)
    throw new HttpError(401, "Anmeldung ungültig");
  return claims.sub;
}

async function oauth(request, env) {
  const b = await readJson(request);
  const cfg = OIDC[b.provider];
  const clientId = cfg ? env[cfg.env] || "" : "";
  if (!clientId) throw new HttpError(501, "Anmeldung mit Google/Apple ist hier nicht eingerichtet");
  const subject = await verifyIdToken(b.provider, b.id_token, clientId);
  let row = await env.DB.prepare("SELECT id, name FROM accounts WHERE provider=? AND subject=?").bind(b.provider, subject).first();
  if (!row) {
    const res = await env.DB.prepare("INSERT INTO accounts (name, password, provider, subject, created_at) VALUES (NULL, NULL, ?, ?, ?)")
      .bind(b.provider, subject, Math.floor(Date.now() / 1000)).run();
    row = { id: res.meta.last_row_id, name: null };
  }
  return { name: row.name, session: await newSession(env, row.id) };
}

async function logout(request, env) {
  const token = (request.headers.get("Authorization") || "").replace(/^Bearer\s+/, "").trim();
  await env.DB.prepare("DELETE FROM sessions WHERE token_hash=?").bind(await sha256(token)).run();
  return { ok: true };
}

async function deleteAccount(request, env) {
  const id = await accountOf(request, env);
  await env.DB.batch([
    env.DB.prepare("DELETE FROM saves WHERE account_id=?").bind(id),
    env.DB.prepare("DELETE FROM sessions WHERE account_id=?").bind(id),
    env.DB.prepare("DELETE FROM accounts WHERE id=?").bind(id),
  ]);
  return { deleted: true };
}

async function getSave(request, env) {
  const id = await accountOf(request, env);
  const row = await env.DB.prepare("SELECT data, updated_at FROM saves WHERE account_id=?").bind(id).first();
  return row ? { profile: JSON.parse(row.data), updated_at: row.updated_at } : { profile: null, updated_at: 0 };
}

async function putSave(request, env) {
  const id = await accountOf(request, env);
  const b = await readJson(request);
  if (!b || typeof b.profile !== "object" || b.profile === null || Array.isArray(b.profile)) throw new HttpError(422, "profile: JSON-Objekt erwartet");
  const data = JSON.stringify(b.profile);
  if (data.length > MAX_SAVE_CHARS) throw new HttpError(413, "Spielstand zu groß");
  const now = Math.floor(Date.now() / 1000);
  await env.DB.prepare("INSERT INTO saves (account_id, data, updated_at) VALUES (?,?,?) ON CONFLICT(account_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at")
    .bind(id, data, now).run();
  return { updated_at: now };
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request, env);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    const url = new URL(request.url);
    try {
      if (url.pathname === "/v1/health" && request.method === "GET") return json({ ok: true }, 200, cors);
      if (url.pathname === "/v1/scores" && request.method === "POST") return json(await submit(request, env), 200, cors);
      if (url.pathname === "/v1/leaderboard" && request.method === "GET") return json(await leaderboard(url, env), 200, cors);
      if (url.pathname === "/v1/me" && request.method === "DELETE") return json(await deleteMine(request, env), 200, cors);
      if (url.pathname === "/v1/config" && request.method === "GET")
        return json({ google_client_id: env.GOOGLE_CLIENT_ID || "", apple_client_id: env.APPLE_CLIENT_ID || "" }, 200, cors);
      if (url.pathname === "/v1/account/register" && request.method === "POST") return json(await register(request, env), 200, cors);
      if (url.pathname === "/v1/account/login" && request.method === "POST") return json(await login(request, env), 200, cors);
      if (url.pathname === "/v1/account/oauth" && request.method === "POST") return json(await oauth(request, env), 200, cors);
      if (url.pathname === "/v1/account/logout" && request.method === "POST") return json(await logout(request, env), 200, cors);
      if (url.pathname === "/v1/account" && request.method === "DELETE") return json(await deleteAccount(request, env), 200, cors);
      if (url.pathname === "/v1/save" && request.method === "GET") return json(await getSave(request, env), 200, cors);
      if (url.pathname === "/v1/save" && request.method === "PUT") return json(await putSave(request, env), 200, cors);
      const m = url.pathname.match(/^\/v1\/scores\/(\d+)$/);
      if (m && request.method === "DELETE") return json(await adminDelete(request, env, Number(m[1])), 200, cors);
      return json({ detail: "Not Found" }, 404, cors);
    } catch (e) {
      if (e instanceof HttpError) return json({ detail: e.detail }, e.status, cors);
      console.error(e);
      return json({ detail: "interner Fehler" }, 500, cors);
    }
  },
};
