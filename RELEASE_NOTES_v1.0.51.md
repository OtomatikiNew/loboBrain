# Release notes — Homeassistant Sports Club Dashboard API v1.0.47 → v1.0.51

## Objective

This range of versions fixes a production bug reported for a Taykus club: forcing a court light ON from the frontend turned it on for an instant and then reverted to OFF on its own, with no visible cause on the frontend or backend side. The investigation traced this — and several related problems found along the way — to how the add-on manages its own state inside Home Assistant, not to anything in OK Cloud's backend or MQTT delivery.

Five review passes were done against the actual shipped code (not just against the intended diff) before this was considered production-ready. Each pass found something real. The full list is below, grouped by theme rather than by commit, since several commits touched the same underlying issue from different angles.

## Root causes found

### 1. `clear_all_entities()` deleted every `binary_sensor.*` in the whole Home Assistant instance, on every add-on restart

Confirmed directly in production logs: entities with no relation to LoboBrain — `binary_sensor.alguna_pista_en_manual`, `binary_sensor.permiso_iluminacion_solar`, `binary_sensor.remote_ui`, `binary_sensor.estado_web_srlobo`, several Shelly sensors — were deleted every time the add-on restarted, because the function filtered only on `'binary_sensor' in entity_id`, with no concept of ownership.

A second, even more dangerous copy of the same function existed in `syltek_integration.py`, with **no filter at all** — it deleted every entity in the whole instance, regardless of domain. That file is not imported or instantiated anywhere in this repository (confirmed by search), but was left in place and neutralized in case an external AppDaemon config still references it by class name.

**Fix:** `clear_all_entities()` removed entirely from `__main__.py`. The `syltek_integration.py` copy turned into a no-op with a warning log and a deprecation notice at the top of the file.

### 2. `homeassistant.local:8123` (mDNS) instead of the Supervisor proxy

The add-on talked to Home Assistant Core over `http://homeassistant.local:8123`, an mDNS hostname. The officially documented, network-stable way for an add-on to reach Core is the Supervisor proxy (`http://supervisor/core`), authenticated with `SUPERVISOR_TOKEN`, which the Supervisor injects automatically for any add-on with `homeassistant_api: true` in `config.yaml`.

**Fix:** REST calls, the internal WebSocket connection, and `middleware.py`'s token-validation endpoint all migrated to the Supervisor proxy. `config.yaml` gained `homeassistant_api: true`.

### 3. The retry mechanism's own GET was gating the POST that would have recreated the entity

This was the most important bug, and the reason the original fix for #4 below didn't fully work on the first attempt. `fetch_data_with_light_id()` (and, identically, `fetch_data_with_door_id()`) did:

```python
if GET(entity) == 200:
    POST(entity, new_state)
```

If the entity doesn't exist — which is exactly the case right after Home Assistant Core restarts, since these are synthetic REST-API states with nothing to recreate them automatically — the GET returns 404, the POST (which would have created the entity, HA returns 201) never runs, and any retry mechanism built on top of this function just re-runs the same failing GET forever without ever making progress.

**Fix:** the GET is now purely optional, used only to refresh `friendly_name` when it succeeds. POST always runs, using a `LIGHT_FRIENDLY_NAME_MAP` / `DOOR_FRIENDLY_NAME_MAP` (populated from OK Cloud data already available at startup) as the name source when the entity doesn't exist yet.

### 4. A plain Core restart, with no light/door event arriving during it, left every entity gone forever

The retry mechanism added to fix "a command is lost while HA is unreachable" only covers commands that actually arrive during the outage. It does not cover a Core restart during which nothing happens — no reservation changes, nobody touches a light — which is the common case. The `binary_sensor.*` entities LoboBrain creates are synthetic REST states, not entities backed by a real HA integration, so Core restarting silently erases all of them with nothing to bring them back.

**Fix:** two in-memory mechanisms, deliberately kept lightweight (no SQLite, no state machine — LoboBrain is deprecated in favor of `automation_bridge` in SR.Lobo v2.0, see the companion document in `srlobo-2.0`):

- `last_light_states`: the most recent known-good desired state of every light, updated on every write attempt regardless of success, seeded from the OK Cloud snapshot at startup.
- `ha_core_recovery_watcher()`: a background worker, polling every 15s, that detects Core coming back and replays every entry from `last_light_states` so the existing retry worker recreates every light. Detection uses two checks, not one: the general `/api/` endpoint transitioning unavailable → available, **and** a sentinel check on one known entity (`GET binary_sensor.pista_1`) even when the general check reports available — because a restart fast enough to complete between two 15-second polls shows as `True → True` on the general check alone, while the entity itself is still gone. This exact scenario was hit and correctly handled in the production verification test (see below).

The replay itself uses `setdefault()`, not `update()`, when merging into the pending-writes queue, so it never overwrites a more recent state that arrived over MQTT in the small window between taking the snapshot and applying it — the "last state always wins" guarantee holds through a recovery replay too.

### 5. WebSocket response-handling bug (pre-existing, found while working in this code)

Inside the HA WebSocket receive loop, `response_dict2 = json.loads(message)` parsed the *original dashboard message* on every iteration instead of `msg_response`, the reply just received from HA — so the branch logic reading `response_dict2['type']` never actually reflected what HA sent back. One-line fix: parse `msg_response`.

### 6. Inconsistent brightness for Taykus `"true"`/`"false"` string payloads

The manual string-payload branch computed brightness with a literal `parsed_payload == 'on'` check, while the `state` field itself goes through `normalize_ha_light_state()`, which also treats `"true"`/`"false"` as on/off. A payload of `"true"` fell through the literal check to `brightness=0` while ending up `state="on"` elsewhere — an inconsistent on-with-zero-brightness result. Now both use the same central normalizer.

### 7. Several tokens logged in plaintext

Found and removed across three review passes, since they kept surfacing one at a time as different code paths were reviewed:

- The dashboard/user's access token, in the internal WebSocket handler.
- The long-lived HA access token (`sys.argv[2]`, still passed by `run.sh` for backward compatibility), in `updateEntityState()` and in `run.sh` itself (`echo "$(bashio::config 'home_assistant_access_token')"`).
- The OK Cloud access token, in `db.py`'s `getDoors()` and in `run.sh` (`echo "$(bashio::config 'ok_cloud_access_token')"`).

All five active `sys.argv[2]` call sites (WebSocket, `getEntityState`, `getDoorState`, `getDoorStateByEntityId`, `deleteDoorFromHa`) also migrated to `home_assistant_access_key` (sourced from `SUPERVISOR_TOKEN` with a `sys.argv[2]` fallback), for consistency.

### 8. Missing timeouts

15 active HTTP calls to Home Assistant had no `timeout=`, meaning a hung connection could block the add-on indefinitely. All given `timeout=(3, 5)`.

## Production verification

After deploying 1.0.51 to the pilot Taykus club, a real Home Assistant Core restart was performed and the add-on log confirmed the full intended behavior end to end:

- Core going down: Supervisor returned `502` for several seconds; an event that arrived during that window (a court light change) got both GET and POST failures and was correctly kept pending for retry, not lost.
- Core coming back: the retry worker found `pista_3` missing (`GET → 404`), created it (`POST → 201`), consistent with fix #3.
- The recovery watcher fired separately and correctly identified the `True → True` blind spot case: the general `/api/` check already reported available, but the sentinel check on `pista_1` still came back 404 (`sentinel_missing=True`), triggering a full replay of all 3 known lights.
- All three courts and the door ended up correctly recreated and continued responding normally to further ON/OFF commands afterward (`GET 200 → POST 200`), confirming this isn't just a one-time recovery but a fully-working add-on post-restart.

## What was deliberately left out of scope

Documented for awareness, not fixed, to keep this release focused:

- Several active `db.py` calls to the OK Cloud backend (`getDoors`, `getLights`, `updateLightMode`, `updateMinLightLevel`, etc.) still lack a request timeout. Unrelated to the HA-restart bug this release targets.
- `entity_id` validation (`_sanitize_entity_suffix`) strips unsafe characters rather than rejecting the input outright. Works correctly for path-injection safety, but a stricter `raise ValueError` design would be cleaner.
- `WebSocket failed` still appears in the add-on log on startup; not yet diagnosed, and did not block any of the fixes above (light/door control goes over REST + MQTT, not this WebSocket).

## Files modified

- `homeassistant_club_dashboard_api/config.yaml`
- `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/__main__.py`
- `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/db.py`
- `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/middleware.py`
- `homeassistant_club_dashboard_api/homeassistant_club_dashboard_api/syltek_integration.py`
- `homeassistant_club_dashboard_api/run.sh`

## Compatibility

MQTT topics, stable entity naming (`pista_N` / `puerta_N`), and the backend ID mapping are all unchanged. The add-on now requires the `homeassistant_api: true` permission (prompts for re-confirmation on update, this is expected). `home_assistant_access_token` is still accepted as a config option for backward compatibility but is no longer the primary token source; `SUPERVISOR_TOKEN` is used when available.

## Related

A companion document, aimed at the team building `automation_bridge` for SR.Lobo v2.0 (the designated replacement for this add-on), captures these findings as design requirements rather than a bug list: `docs/architecture/lessons-from-lobobrain.md` in the `srlobo-2.0` repository.
