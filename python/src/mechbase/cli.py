"""`mechbase` command line — readings, points and spectra from a terminal.

    mechbase login                      # once; stores a token in ~/.config/mechbase/config.json
    mechbase points --asset 1
    mechbase readings 2
    mechbase reading show 2 766         # values, state and the top spectrum peaks
    mechbase reading delete 2 767
    mechbase point show 2               # running, stale, alarm limits, last 7 days
    mechbase findings --status open
    mechbase finding ack <uuid> --wo WO-1234
    mechbase export measurements --point 2 -o readings.csv
    mechbase photo add point 2 pump.jpg
    mechbase comment add 1 "Bearing noise after restart" --point 2
    mechbase doc add 1 manual.pdf --kind manual
    mechbase alarm set 2 --minor 2.8 --major 7.1
    mechbase zone guest on --all        # QR guest view on every zone
    mechbase asset-type set QB-STD --name "QB pump" ; mechbase asset-type checklist QB-STD list.json
    mechbase asset set-type QB-STD 1 2 3
    mechbase devices                    # MaintNodes: online, health, channels
    mechbase tunnel open logo           # remote access to a device's site

Every command takes --json for scripting. MECHBASE_TOKEN / MECHBASE_URL /
MECHBASE_INSTALLATION override the stored config and are never written to it
(`login` stores the URL it signed in to, wherever that came from).
"""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import html
import json
import os
import platform
import re
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import httpx

from . import Mechbase
from ._http import HttpClient
from .errors import MechbaseError, NotFoundError

STATUS = {1: "good", 2: "elevated", 3: "minor", 4: "major"}
# Headline values for `readings`; `reading show` prints everything.
HEADLINE = ("value", "rms", "peak", "vel_10hz", "crest_factor", "kurtosis", "temperature")

def _config_path() -> Path:
    # Read at each call, not at import, so XDG_CONFIG_HOME set later (tests, wrappers) is honoured.
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "mechbase" / "config.json"


def _stored() -> dict:
    """The config file alone, without the MECHBASE_* overrides."""
    try:
        data = json.loads(_config_path().read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load() -> dict:
    cfg = _stored()
    for key, env in (("token", "MECHBASE_TOKEN"), ("url", "MECHBASE_URL"), ("installation", "MECHBASE_INSTALLATION")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    cfg.setdefault("url", Mechbase.DEFAULT_BASE_URL)
    return cfg


def _save(**changes) -> None:
    """Apply changes to the stored file (None removes a key). Env overrides are never written."""
    cfg = _stored()
    for key, value in changes.items():
        if value is None:
            cfg.pop(key, None)
        else:
            cfg[key] = value
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_private(path, json.dumps(cfg, indent=2).encode())


def _write_private(path: Path, data: bytes) -> None:
    """Write a file that is 0600 from its creation, never briefly readable by others."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if hasattr(os, "fchmod"):  # absent on Windows before 3.13
        os.fchmod(fd, 0o600)  # an existing file keeps its mode through O_CREAT
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def _client(cfg: dict) -> Mechbase:
    if not cfg.get("token"):
        sys.exit("Not signed in. Run: mechbase login")
    return Mechbase(token=cfg["token"], base_url=cfg["url"])


def _inst(args, cfg, client):
    iid = args.installation or cfg.get("installation") or client.me().current_installation_id
    if iid is None:
        sys.exit("No installation selected. Run: mechbase use <id>")
    return client.for_installation(int(iid))


def _aware(s: str | None) -> str | None:
    """ISO date/time as the API wants it: with an offset (local time when none is given)."""
    if s is None:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        sys.exit(f"Not an ISO date/time: {s}")
    return (dt if dt.tzinfo else dt.astimezone()).isoformat()


def _out(args, rows: list[dict], cols: list[str]) -> None:
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return
    widths = [max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols] if rows else [len(c) for c in cols]
    print("  ".join(c.upper().ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(w) for c, w in zip(cols, widths)))


def peaks(freq: list[float], amp: list[float], *, top: int = 10, line_hz: float = 50.0) -> list[dict]:
    """Top local maxima, each tagged when it sits on a mains multiple (k × line_hz).

    ponytail: plain local-max scan; no interpolation or noise floor — add when
    peaks need sub-bin accuracy or the list fills with grass.
    """
    df = freq[1] - freq[0] if len(freq) > 1 else 0
    found = [
        (freq[i], amp[i])
        for i in range(1, len(amp) - 1)
        if freq[i] > 0 and amp[i] > amp[i - 1] and amp[i] >= amp[i + 1]
    ]
    found.sort(key=lambda p: p[1], reverse=True)
    out = []
    for f, a in found[:top]:
        k = round(f / line_hz)
        # within half a bin: a mains line lands on k×line_hz, a shaft speed near it doesn't
        tag = f"{k}×{line_hz:g} Hz (electrical)" if k and abs(f - k * line_hz) <= df / 2 else ""
        out.append({"hz": round(f, 2), "amplitude": round(a, 4), "note": tag})
    return out


# --- commands ---------------------------------------------------------------


def cmd_login(args, cfg):
    email = args.email or input("Email: ")
    password = getpass.getpass("Password: ")
    url = args.url or cfg["url"]
    with HttpClient(token=None, base_url=url) as http:
        body = http.request(
            "POST",
            "/api/auth/token",
            json={"username": email, "password": password, "device_id": f"cli-{platform.node()}"},
        )
    old = _stored()
    changes = {"token": body["token"], "url": url}  # the URL the token was issued by, even if from MECHBASE_URL
    if old.get("url", Mechbase.DEFAULT_BASE_URL) != url:
        changes["installation"] = None  # an installation id means nothing on another server
    _save(**changes)  # save first: a slow or broken revoke below must not lose the new token
    _revoke(old)  # don't leave the replaced token live on the server
    me = Mechbase(token=body["token"], base_url=url).me()
    print(f"Signed in as {me.user.email or me.user.username} on {url}")
    _warn_env("MECHBASE_TOKEN")


def cmd_whoami(args, cfg):
    me = _client(cfg).me()
    current = int(cfg.get("installation") or me.current_installation_id or 0)
    rows = [{"id": i.installation_id, "name": i.name, "current": "*" if i.installation_id == current else ""}
            for i in me.installations]
    if not args.json:
        print(f"{me.user.email or me.user.username} @ {cfg['url']}")
    _out(args, rows, ["current", "id", "name"])


def cmd_use(args, cfg):
    _save(installation=args.installation_id)
    _warn_env("MECHBASE_INSTALLATION")
    print(f"Using installation {args.installation_id}")


def cmd_assets(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    rows = [{"id": a.asset_id, "name": a.name, "status": STATUS.get(a.status, a.status)} for a in inst.assets.list(q=args.q, limit=args.limit)]
    _out(args, rows, ["id", "name", "status"])


def cmd_points(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    pts = inst.measurement_points.list(q=args.q, asset_id=args.asset, limit=args.limit)
    rows = [{"id": p.point_id, "asset": p.asset_id, "name": p.name, "type": p.transducer_type,
             "unit": p.measurement_unit_code, "status": STATUS.get(p.status, p.status)} for p in pts]
    _out(args, rows, ["id", "asset", "name", "type", "unit", "status"])


def _reading_row(m) -> dict:
    data = {k: m.data[k] for k in HEADLINE if k in m.data} or m.data
    vals = ", ".join(f"{k}={v:.3g}" if isinstance(v, (int, float)) else f"{k}={v}" for k, v in data.items())
    return {"reading": m.point_sequence, "when": m.created_at[:16].replace("T", " "), "state": m.status, "values": vals}


def cmd_readings(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    ms = inst.measurements.list_for_point(args.point, limit=args.limit)
    if args.json:
        print(json.dumps([m.__dict__ for m in ms], indent=2, default=str))
        return
    _out(args, [_reading_row(m) for m in ms], ["reading", "when", "state", "values"])


def cmd_reading_show(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    m = inst.measurements.get(args.point, args.reading)
    spec = inst.measurements.spectra(m.uuid) if args.peaks else {}
    found = peaks(spec.get("freq_hz") or [], spec.get(args.signal) or [], top=args.peaks, line_hz=args.line_hz)
    if args.json:
        print(json.dumps({**m.__dict__, "peaks": found, "signal": args.signal}, indent=2, default=str))
        return
    r = _reading_row(m)
    print(f"Point {args.point} · reading {m.point_sequence} · {r['when']} · {m.status.upper()}")
    width = max(map(len, [*m.data, "file"]))
    for k, v in m.data.items():
        print(f"  {k:<{width}}  {v}")
    if m.file_url:
        print(f"  {'file':<{width}}  {m.file_url}")
    if args.peaks:
        if found:
            print(f"\nTop {len(found)} {args.signal} peaks:")
            _out(args, found, ["hz", "amplitude", "note"])
        else:
            print("\nNo spectrum (reading has no waveform).")


def cmd_reading_delete(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    if not args.yes:
        m = inst.measurements.get(args.point, args.reading)
        print(_reading_row(m))
        if input(f"Delete reading {args.reading} of point {args.point}? It cannot be undone. [y/N] ").lower() != "y":
            sys.exit("Cancelled.")
    inst.measurements.delete(args.point, args.reading)
    print(f"Deleted reading {args.reading} of point {args.point}.")


def _revoke(stored: dict) -> None:
    """Revoke a stored token (not a MECHBASE_TOKEN override) against the URL it was issued by."""
    if stored.get("token"):
        try:
            Mechbase(token=stored["token"], base_url=stored.get("url") or Mechbase.DEFAULT_BASE_URL).revoke_token()
        except (MechbaseError, httpx.HTTPError, httpx.InvalidURL):
            pass  # already revoked, server gone or URL garbage: forget it locally anyway


def _warn_env(var: str) -> None:
    if os.environ.get(var):
        print(f"{var} is still set in this shell and overrides the saved config.", file=sys.stderr)


def cmd_logout(args, cfg):
    _revoke(_stored())
    _save(token=None)
    print("Signed out.")
    _warn_env("MECHBASE_TOKEN")


def cmd_point_show(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    p = inst.measurement_points.get(args.point)
    ctx = inst.measurement_points.context(args.point)
    if args.json:
        print(json.dumps({**dataclasses.asdict(p), "context": ctx}, indent=2, default=str))
        return
    print(f"Point {p.point_id} · {p.name} · {p.transducer_type} · {STATUS.get(p.status, p.status).upper()}")
    running = {True: "running", False: "stopped", None: "unknown"}[ctx.get("running")]
    print(f"  machine    {running}" + (f" (since {ctx['running_at'][:16].replace('T', ' ')})" if ctx.get("running_at") else ""))
    if ctx.get("stale_since"):
        print(f"  stale      no reading since {ctx['stale_since'][:16].replace('T', ' ')}")
    lim = ctx.get("limits") or {}
    if lim.get("minor") is not None or lim.get("major") is not None:
        print(f"  limits     minor {lim.get('minor')} · major {lim.get('major')} {ctx.get('unit', '')}")
    week = [b["v"] for b in ctx.get("week") or [] if b.get("v") is not None]
    if week:
        print(f"  7 days     {ctx.get('data_key')} min {min(week):.3g} · max {max(week):.3g} · last {week[-1]:.3g} {ctx.get('unit', '')}")
    if p.reference_photo_uuid:
        ref = next((ph.url for ph in p.photos if ph.uuid == p.reference_photo_uuid), "")
        print(f"  photo      {ref}")


def cmd_findings(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    fs = inst.findings.list(status=args.status, asset_id=args.asset, point_id=args.point, limit=args.limit)
    if args.json:
        print(json.dumps([dataclasses.asdict(f) for f in fs], indent=2, default=str))
        return
    rows = [{"finding": f.uuid, "when": f.created_at[:10], "status": f.status, "severity": f.severity,
             "asset": f.asset_name, "point": f.point_name, "fault": f.fault_type_display or f.fault_type,
             "work order": f.work_order_ref} for f in fs]
    _out(args, rows, ["finding", "when", "status", "severity", "asset", "point", "fault", "work order"])


def cmd_finding_set(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    if args.action == "ack":
        f = inst.findings.acknowledge(args.finding, work_order_ref=args.wo)
    else:
        f = inst.findings.close(args.finding, work_order_ref=args.wo)
    if args.json:
        print(json.dumps(dataclasses.asdict(f), indent=2, default=str))
        return
    print(f"{f.asset_name} · {f.fault_type_display or f.fault_type}: {f.status}" + (f" ({f.work_order_ref})" if f.work_order_ref else ""))


def cmd_export(args, cfg):
    if args.dataset != "measurements" and (args.asset or args.point):
        sys.exit("--asset and --point only filter the measurements export.")
    inst = _inst(args, cfg, _client(cfg))
    filters = {k: v for k, v in {"asset_id": args.asset, "point_id": args.point,
                                 "created_from": _aware(args.since), "created_to": _aware(args.until)}.items()
               if v is not None}
    job = inst.exports.create(args.dataset, format=args.format, filters=filters)
    out = Path(args.output or f"{args.dataset}.{args.format}")
    # ponytail: fixed 2 s poll, no timeout; exports finish in seconds to minutes
    while (st := inst.exports.status(job["job_uuid"]))["state"] in ("pending", "running"):
        time.sleep(2)
    if st["state"] != "done":
        sys.exit(f"Export {st['state']}: {st.get('error') or 'no file'}")
    out.write_bytes(inst.exports.download(job["job_uuid"]))
    if args.json:
        print(json.dumps({**st, "path": str(out)}, indent=2, default=str))
        return
    print(f"Wrote {st.get('row_count')} rows to {out}")


def cmd_photo_add(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    res = inst.assets if args.kind == "asset" else inst.measurement_points
    f = res.add_photo(args.id, args.file)
    print(json.dumps(f.__dict__, indent=2, default=str) if args.json else f"Added photo {f.uuid} to {args.kind} {args.id}.")


def cmd_photo_delete(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    res = inst.assets if args.kind == "asset" else inst.measurement_points
    if not args.yes and input(f"Delete photo {args.photo} of {args.kind} {args.id}? [y/N] ").lower() != "y":
        sys.exit("Cancelled.")
    res.delete_photo(args.id, args.photo)
    print(f"Deleted photo {args.photo} of {args.kind} {args.id}.")


def cmd_comments(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    cs = inst.comments.list(args.asset, limit=args.limit)
    if args.json:
        print(json.dumps(cs, indent=2))
        return
    for c in reversed(cs):  # oldest first, like the thread
        refs = ", ".join(f"point {r['point_id']}" + (f" reading {r['point_sequence']}" if r.get("point_sequence") else "")
                         for r in c["references"])
        tags = " · finding" if c["is_finding"] else ""
        print(f"#{c['id']} {c['created_at'][:16].replace('T', ' ')} {c['author_name']}{tags}" + (f" ({refs})" if refs else ""))
        print(f"  {c['body_text'].strip()}")


def cmd_comment_add(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    if args.reading and not args.point:
        sys.exit("--reading needs --point.")
    refs = [{"point_id": args.point, "point_sequence": args.reading}] if args.point else None
    c = inst.comments.create(args.asset, f"<div>{html.escape(args.text)}</div>", references=refs)
    print(json.dumps(c, indent=2) if args.json else f"Posted comment #{c['id']} on asset {args.asset}.")


def cmd_comment_delete(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    if not args.yes and input(f"Delete comment #{args.comment} on asset {args.asset}? [y/N] ").lower() != "y":
        sys.exit("Cancelled.")
    inst.comments.delete(args.asset, args.comment)
    print(f"Deleted comment #{args.comment}.")


def cmd_docs(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    docs = inst.documents.list(args.asset)
    if args.json:
        print(json.dumps(docs, indent=2))
        return
    _out(args, [{**d, "added": d["created_at"][:10]} for d in docs], ["uuid", "added", "kind", "name"])


def cmd_doc_add(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    d = inst.documents.add(args.asset, args.file, kind=args.kind)
    print(json.dumps(d, indent=2) if args.json else f"Added {d['kind']} {d['name']} ({d['uuid']}) to asset {args.asset}.")


def cmd_doc_delete(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    if not args.yes and input(f"Delete document {args.document} of asset {args.asset}? [y/N] ").lower() != "y":
        sys.exit("Cancelled.")
    inst.documents.delete(args.asset, args.document)
    print(f"Deleted document {args.document}.")


def cmd_zone_guest(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    if args.all == bool(args.zones):
        sys.exit("Give zone ids or --all.")
    on = args.state == "on"
    n = inst.zones.set_guest_view(on, zone_ids=args.zones or None, all=args.all)
    print(json.dumps({"zones": args.zones or None, "updated": n, "guest_view": on}) if args.json else f"Guest view {args.state} for {n} zone(s).")


def cmd_asset_types(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    rows = [{"code": t.code, "name": t.name, "manufacturer": t.manufacturer, "checks": len(t.checklist),
             "assets": t.asset_count, "docs": t.document_count} for t in inst.asset_types.list()]
    _out(args, rows, ["code", "name", "manufacturer", "checks", "assets", "docs"])


def cmd_asset_type_set(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    try:
        inst.asset_types.get(args.code)
        verb = "Updated"
    except NotFoundError:
        if not args.name:
            sys.exit(f"No asset type {args.code} yet: give --name to create it.")
        verb = "Created"
    t = inst.asset_types.upsert(args.code, name=args.name, manufacturer=args.manufacturer)
    print(json.dumps(dataclasses.asdict(t), indent=2) if args.json else f"{verb} asset type {t.code} ({t.name}).")


def cmd_asset_type_checklist(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    items = json.loads(Path(args.file).read_text())
    if not isinstance(items, list):
        sys.exit("The checklist file must hold a JSON list.")
    t = inst.asset_types.update(args.code, checklist=items)  # PATCH: a mistyped code is a 404, not a new type
    print(json.dumps(dataclasses.asdict(t), indent=2) if args.json else f"Asset type {t.code}: {len(t.checklist)} checks.")


def cmd_asset_type_doc_add(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    d = inst.asset_types.add_document(args.code, args.file, kind=args.kind)
    print(json.dumps(d, indent=2) if args.json else f"Added {d['kind']} {d['name']} ({d['uuid']}) to type {args.code}.")


def cmd_asset_set_type(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    code = None if args.clear else args.targets[0]
    try:
        ids = [int(i) for i in (args.targets if args.clear else args.targets[1:])]
    except ValueError:
        sys.exit("Asset ids must be numbers.")
    if not ids:
        sys.exit("Give a type code and at least one asset id (or --clear and ids).")
    done, failed = [], {}
    for aid in ids:  # one call per asset: report each so a failure part-way is not a mystery
        try:
            inst.assets.update(aid, asset_type=code)
            done.append(aid)
        except MechbaseError as e:
            failed[aid] = str(e)
    if args.json:
        print(json.dumps({"assets": done, "asset_type": code, "failed": failed}))
    else:
        print(f"{'Cleared the type of' if code is None else f'Set type {code} on'} {len(done)} asset(s)"
              + (f": {', '.join(map(str, done))}." if failed and done else "."))
        for aid, err in failed.items():
            print(f"Asset {aid} not changed: {err}", file=sys.stderr)
    if failed:
        sys.exit(1)


def cmd_alarms(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    rules = inst.alarm_rules.list(args.point)
    if args.json:
        print(json.dumps(rules, indent=2))
        return
    rows = [{"scope": r["scope"], "method": r["method"], "value": r["effective_data_key"], "direction": r["direction"],
             "minor": r.get("minor_threshold"), "major": r.get("major_threshold"), "source": r.get("source") or ""}
            for r in rules]
    _out(args, rows, ["scope", "method", "value", "direction", "minor", "major", "source"])


def _own_threshold(inst, point_id):
    return next((r for r in inst.alarm_rules.list(point_id) if r["scope"] == "point" and r["method"] == "threshold"), None)


def cmd_alarm_set(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    own = _own_threshold(inst, args.point)
    if own:
        r = inst.alarm_rules.update(args.point, own["uuid"], minor_threshold=args.minor, major_threshold=args.major,
                                    data_key=args.key, direction=args.direction)
    else:
        if args.minor is None or args.major is None:
            # a point rule replaces the default whole: a missing limit would switch that alarm off
            sys.exit(f"Point {args.point} has no threshold of its own yet: give both --minor and --major.")
        r = inst.alarm_rules.create(args.point, minor_threshold=args.minor, major_threshold=args.major,
                                    data_key=args.key or "", direction=args.direction or "high")
    if args.json:
        print(json.dumps(r, indent=2))
        return
    print(f"Point {args.point}: {r['effective_data_key']} minor {r.get('minor_threshold')} · major {r.get('major_threshold')} ({r['direction']}).")


def cmd_alarm_clear(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    own = _own_threshold(inst, args.point)
    if not own or own.get("source") == "iso_10816":  # the ISO default is inherited, not an override
        sys.exit(f"Point {args.point} has no threshold of its own.")
    inst.alarm_rules.delete(args.point, own["uuid"])
    print(f"Point {args.point} is back on its default limits.")


_JSON_SCALAR = re.compile(r'-?\d+(\.\d+)?|null|true|false|".*"')


def _fields(pairs: list[str]) -> dict:
    """key=value pairs. A plain number (2, 1.5), null, true or false is sent as JSON, and a
    quoted value ('"1.50"') as that string; anything else (SN-12e4, 0x10) as typed."""
    out = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            sys.exit(f"Expected key=value, got: {pair}")
        out[key] = json.loads(value) if _JSON_SCALAR.fullmatch(value) else value
    return out


def _matches(items: list[dict], ref: str, keys: tuple[str, ...]) -> list[dict]:
    """Items whose name (keys[1:]) is `ref`, else whose uuid (keys[0]) starts with it; case and
    dashes don't matter."""
    ref_l = ref.lower()
    prefix = ref_l.replace("-", "")
    if not prefix:
        return []  # an empty ref would otherwise match everything
    hits = [i for i in items if any(str(i.get(k) or "").lower() == ref_l for k in keys[1:])]
    return hits or [i for i in items if str(i[keys[0]]).replace("-", "").lower().startswith(prefix)]


def _pick(items: list[dict], ref: str, keys: tuple[str, ...], what: str) -> dict:
    """The one item `ref` names (see _matches), or exit."""
    hits = _matches(items, ref, keys)
    if len(hits) != 1:
        sys.exit(f"No {what} matches {ref}." if not hits else f"{ref} matches {len(hits)} {what}s; give more of the uuid.")
    return hits[0]


def _ago(ts: str | None) -> str:
    if not ts:
        return "never"
    # Python 3.10's fromisoformat takes no "Z"
    secs = int((datetime.now().astimezone() - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds())
    for unit, size in (("d", 86400), ("h", 3600), ("min", 60)):
        if secs >= size:
            return f"{secs // size} {unit} ago"
    return "just now"


def cmd_devices(args, cfg):
    devices = _inst(args, cfg, _client(cfg)).devices.list()
    if args.json:
        print(json.dumps(devices, indent=2))
        return
    rows = [{"device": d["name"], "uuid": d["node_uuid"][:8], "state": "online" if d["is_online"] else "OFFLINE",
             "last seen": _ago(d["last_seen_at"]), "warnings": " ".join(d["health_warnings"]),
             "channels": sum(len(g["channels"]) for g in d["groups"]), "tunnels": len(d["tunnels"])} for d in devices]
    _out(args, rows, ["device", "uuid", "state", "last seen", "warnings", "channels", "tunnels"])


def _tunnel_target(t: dict) -> str:
    return t["web_url"] if t["kind"] == "http" else f"stcp 127.0.0.1:{t['local_port']} (mechbase tunnel file {t['uuid'][:8]})"


def cmd_device_show(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    d = _pick(inst.devices.list(), args.device, ("node_uuid", "name"), "device")
    if args.json:
        print(json.dumps(d, indent=2))
        return
    state = "online" if d["is_online"] else "OFFLINE"
    print(f"{d['name']} ({d['node_uuid']}): {state}, last seen {_ago(d['last_seen_at'])}"
          + (f", {' '.join(d['health_warnings'])}" if d["health_warnings"] else ""))
    if d.get("health_url"):
        print(f"Factory health: {d['health_url']}")
    for g in d["groups"]:
        print(f"\nGroup {g['name']} ({g['hardware_type']}, every {g['interval']} s) {g['uuid']}")
        rows = [{"channel": f"CH{c['channel']}", "point": f"{c['point_id']} {c['asset_name']} · {c['point_name']}",
                 "sensor": c["sensor"], "last data": _ago(c["last_seen_at"]), "state": c["state"].upper()}
                for c in g["channels"]]
        _out(args, rows, ["channel", "point", "sensor", "last data", "state"])
    if d["tunnels"]:
        print("\nRemote access")
        for t in d["tunnels"]:
            print(f"  {t['label'] or t['name']}: {_tunnel_target(t)}")


def cmd_device_rename(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    d = _pick(inst.devices.list(), args.device, ("node_uuid", "name"), "device")
    d = inst.devices.rename(d["node_uuid"], args.name)
    print(json.dumps(d, indent=2) if args.json else f"Renamed to {d['name']}.")


def cmd_group_set(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    d = _pick(inst.devices.list(), args.device, ("node_uuid", "name"), "device")
    g = _pick(d["groups"], args.group, ("uuid", "name"), "group")
    d = inst.devices.update_group(d["node_uuid"], g["uuid"], **_fields(args.fields))
    print(json.dumps(d, indent=2) if args.json else f"Updated group {g['name']} on {d['name']}.")


def _tunnel_list(args, cfg, client) -> list[dict]:
    if args.all:
        return client.tunnels.list()
    return [{**t, "device_name": d["name"]} for d in _inst(args, cfg, client).devices.list() for t in d["tunnels"]]


def cmd_tunnels(args, cfg):
    tunnels = _tunnel_list(args, cfg, _client(cfg))
    if args.json:
        print(json.dumps(tunnels, indent=2))
        return
    rows = [{"uuid": t["uuid"][:8], "installation": t.get("installation_name") or "", "device": t["device_name"],
             "name": t["name"], "label": t["label"], "open": _tunnel_target(t)} for t in tunnels]
    _out(args, rows, (["uuid", "installation"] if args.all else ["uuid"]) + ["device", "name", "label", "open"])


def _find_tunnel(args, cfg, client, ref: str) -> dict:
    keys = ("uuid", "name", "label")
    tunnels = _tunnel_list(args, cfg, client)
    if not args.all and not _matches(tunnels, ref, keys):
        tunnels = client.tunnels.list()  # staff: a tunnel outside this installation
    return _pick(tunnels, ref, keys, "tunnel")


def cmd_tunnel_open(args, cfg):
    client = _client(cfg)
    t = _find_tunnel(args, cfg, client, args.tunnel)
    if t["kind"] != "http":
        sys.exit(f"{t['name']} is an stcp tunnel: mechbase tunnel file {t['uuid'][:8]}")
    if not t["web_url"].startswith(("https://", "http://")):
        sys.exit(f"Refusing to open {t['web_url']!r}: not an http(s) URL.")
    print(t["web_url"])
    webbrowser.open(t["web_url"])


def cmd_tunnel_file(args, cfg):
    client = _client(cfg)
    t = _find_tunnel(args, cfg, client, args.tunnel)
    if t["kind"] != "stcp":
        sys.exit(f"{t['name']} is an http tunnel: mechbase tunnel open {t['uuid'][:8]}")
    # The device name is anyone's to set: keep only filename-safe characters.
    device = re.sub(r"[^A-Za-z0-9._-]+", "-", t["device_name"]).strip(".-")[:60] or "device"
    path = Path(args.output or f"{device}-{t['name']}.toml")
    body = client.tunnels.visitor_toml(t["uuid"])
    _write_private(path, body)  # it holds the frps token and the tunnel secret
    print(f"Wrote {path}. Run: frpc -c {path}  then connect to 127.0.0.1:{t['local_port']}")


def cmd_sources(args, cfg):
    sources = _inst(args, cfg, _client(cfg)).sources.list(args.point)
    if args.json:
        print(json.dumps(sources, indent=2))
        return
    rows = [{"uuid": s["uuid"][:8], "type": s["source_type"], "device": s.get("device_name") or s["device_id"],
             "group": (s.get("group") or {}).get("name", ""), "channel": s["channel"], "sensor": s["sensor"],
             "last data": _ago(s["last_seen_at"]), "stale": "STALE" if s.get("stale_since") else ""} for s in sources]
    _out(args, rows, ["uuid", "type", "device", "group", "channel", "sensor", "last data", "stale"])


def _source(inst, point, ref):
    return _pick(inst.sources.list(point), ref, ("uuid",), "source")


def cmd_source_add(args, cfg):
    s = _inst(args, cfg, _client(cfg)).sources.create(args.point, **_fields(args.fields))
    print(json.dumps(s, indent=2) if args.json else f"Added {s['source_type']} source {s['uuid']} to point {args.point}.")


def cmd_source_set(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    s = inst.sources.update(args.point, _source(inst, args.point, args.source)["uuid"], **_fields(args.fields))
    print(json.dumps(s, indent=2) if args.json else f"Updated source {s['uuid']}.")


def cmd_source_delete(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    s = _source(inst, args.point, args.source)
    if not args.yes and input(f"Remove source {s['uuid']} from point {args.point}? [y/N] ").lower() != "y":
        sys.exit("Cancelled.")
    inst.sources.delete(args.point, s["uuid"])
    print(f"Removed source {s['uuid']}.")


# --- wiring -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("-i", "--installation", type=int, help="installation id (default: `mechbase use`, else your current one)")

    p = argparse.ArgumentParser(prog="mechbase", description="Mechbase from the command line.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login", help="sign in and store a token")
    s.add_argument("--email")
    s.add_argument("--url", help=f"server (default {Mechbase.DEFAULT_BASE_URL})")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("whoami", parents=[common], help="who you are and which installations you can see")
    s.set_defaults(fn=cmd_whoami)

    s = sub.add_parser("use", help="set the default installation")
    s.add_argument("installation_id", type=int)
    s.set_defaults(fn=cmd_use)

    s = sub.add_parser("assets", parents=[common], help="list assets")
    s.add_argument("-q", default="", help="search")
    s.add_argument("-n", "--limit", type=int, default=100)
    s.set_defaults(fn=cmd_assets)

    s = sub.add_parser("points", parents=[common], help="list measurement points")
    s.add_argument("--asset", type=int)
    s.add_argument("-q", default="", help="search")
    s.add_argument("-n", "--limit", type=int, default=100)
    s.set_defaults(fn=cmd_points)

    s = sub.add_parser("readings", parents=[common], help="latest readings of a point")
    s.add_argument("point", type=int)
    s.add_argument("-n", "--limit", type=int, default=20)
    s.set_defaults(fn=cmd_readings)

    reading = sub.add_parser("reading", help="one reading").add_subparsers(dest="action", required=True)
    s = reading.add_parser("show", parents=[common], help="values, state and spectrum peaks")
    s.add_argument("point", type=int)
    s.add_argument("reading", type=int, help="the number in the web URL")
    s.add_argument("--peaks", type=int, default=10, help="how many spectrum peaks (0 = skip spectrum)")
    s.add_argument("--signal", choices=["velocity", "acceleration", "envelope"], default="velocity")
    s.add_argument("--line-hz", type=float, default=50.0, help="mains frequency for the electrical tag (60 in the Americas)")
    s.set_defaults(fn=cmd_reading_show)

    s = reading.add_parser("delete", parents=[common], help="delete a reading")
    s.add_argument("point", type=int)
    s.add_argument("reading", type=int)
    s.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    s.set_defaults(fn=cmd_reading_delete)

    s = sub.add_parser("logout", help="revoke the stored token and forget it")
    s.set_defaults(fn=cmd_logout)

    point = sub.add_parser("point", help="one measurement point").add_subparsers(dest="action", required=True)
    s = point.add_parser("show", parents=[common], help="run state, staleness, limits, last 7 days")
    s.add_argument("point", type=int)
    s.set_defaults(fn=cmd_point_show)

    s = sub.add_parser("findings", parents=[common], help="list findings (diagnosed faults)")
    s.add_argument("--status", choices=["open", "acknowledged", "closed"])
    s.add_argument("--asset", type=int)
    s.add_argument("--point", type=int)
    s.add_argument("-n", "--limit", type=int, default=50)
    s.set_defaults(fn=cmd_findings)

    finding = sub.add_parser("finding", help="move a finding on").add_subparsers(dest="action", required=True)
    s = finding.add_parser("ack", parents=[common], help="a work order was raised")
    s.add_argument("finding", help="finding uuid (from `mechbase findings`)")
    s.add_argument("--wo", required=True, help="work order reference")
    s.set_defaults(fn=cmd_finding_set)
    s = finding.add_parser("close", parents=[common], help="the work is done")
    s.add_argument("finding")
    s.add_argument("--wo", help="work order reference")
    s.set_defaults(fn=cmd_finding_set)

    s = sub.add_parser("export", parents=[common], help="export a dataset to a file")
    s.add_argument("dataset", choices=["measurements", "events", "inspections"])
    s.add_argument("--format", choices=["csv", "parquet"], default="csv")
    s.add_argument("--asset", type=int, help="measurements only")
    s.add_argument("--point", type=int, help="measurements only")
    s.add_argument("--since", help="ISO date or date/time (local time unless it has an offset)")
    s.add_argument("--until", help="ISO date or date/time (local time unless it has an offset)")
    s.add_argument("-o", "--output", help="file (default <dataset>.<format>)")
    s.set_defaults(fn=cmd_export)

    photo = sub.add_parser("photo", help="asset and point photos").add_subparsers(dest="action", required=True)
    s = photo.add_parser("add", parents=[common], help="add a photo")
    s.add_argument("kind", choices=["asset", "point"])
    s.add_argument("id", type=int)
    s.add_argument("file")
    s.set_defaults(fn=cmd_photo_add)
    s = photo.add_parser("delete", parents=[common], help="delete a photo")
    s.add_argument("kind", choices=["asset", "point"])
    s.add_argument("id", type=int)
    s.add_argument("photo", help="photo uuid (from `point show --json`)")
    s.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    s.set_defaults(fn=cmd_photo_delete)

    s = sub.add_parser("comments", parents=[common], help="an asset's thread")
    s.add_argument("asset", type=int)
    s.add_argument("-n", "--limit", type=int, default=20)
    s.set_defaults(fn=cmd_comments)
    comment = sub.add_parser("comment", help="post or delete a comment").add_subparsers(dest="action", required=True)
    s = comment.add_parser("add", parents=[common], help="post to an asset's thread")
    s.add_argument("asset", type=int)
    s.add_argument("text")
    s.add_argument("--point", type=int, help="reference a point of this asset")
    s.add_argument("--reading", type=int, help="…and one of its readings (the number in the web URL)")
    s.set_defaults(fn=cmd_comment_add)
    s = comment.add_parser("delete", parents=[common], help="delete your comment")
    s.add_argument("asset", type=int)
    s.add_argument("comment", type=int, help="comment number (from `mechbase comments`)")
    s.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    s.set_defaults(fn=cmd_comment_delete)

    s = sub.add_parser("docs", parents=[common], help="an asset's documents")
    s.add_argument("asset", type=int)
    s.set_defaults(fn=cmd_docs)
    doc = sub.add_parser("doc", help="add or delete a document").add_subparsers(dest="action", required=True)
    s = doc.add_parser("add", parents=[common], help="upload a document to an asset")
    s.add_argument("asset", type=int)
    s.add_argument("file")
    s.add_argument("--kind", default="attachment", choices=["attachment", "drawing", "datasheet", "manual", "check_sheet", "test_report"])
    s.set_defaults(fn=cmd_doc_add)
    s = doc.add_parser("delete", parents=[common], help="delete a document")
    s.add_argument("asset", type=int)
    s.add_argument("document", help="document uuid (from `mechbase docs`)")
    s.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    s.set_defaults(fn=cmd_doc_delete)

    zone = sub.add_parser("zone", help="zone settings").add_subparsers(dest="action", required=True)
    s = zone.add_parser("guest", parents=[common], help="turn the QR guest view on or off for zones")
    s.add_argument("state", choices=["on", "off"])
    s.add_argument("zones", type=int, nargs="*", help="zone ids")
    s.add_argument("--all", action="store_true", help="every zone")
    s.set_defaults(fn=cmd_zone_guest)

    at = sub.add_parser("asset-type", help="asset types (templates)").add_subparsers(dest="action", required=True)
    s = at.add_parser("list", parents=[common], help="list asset types")
    s.set_defaults(fn=cmd_asset_types)
    s = at.add_parser("set", parents=[common], help="create or update a type by code")
    s.add_argument("code")
    s.add_argument("--name")
    s.add_argument("--manufacturer")
    s.set_defaults(fn=cmd_asset_type_set)
    s = at.add_parser("checklist", parents=[common], help="replace a type's checklist from a JSON file")
    s.add_argument("code")
    s.add_argument("file", help="JSON list of checklist items")
    s.set_defaults(fn=cmd_asset_type_checklist)
    atdoc = at.add_parser("doc", help="type documents").add_subparsers(dest="doc_action", required=True)
    s = atdoc.add_parser("add", parents=[common], help="upload a document to a type")
    s.add_argument("code")
    s.add_argument("file")
    s.add_argument("--kind", default="attachment", choices=["attachment", "drawing", "datasheet", "manual", "check_sheet", "test_report"])
    s.set_defaults(fn=cmd_asset_type_doc_add)

    asset = sub.add_parser("asset", help="asset settings").add_subparsers(dest="action", required=True)
    s = asset.add_parser("set-type", parents=[common], help="set (or --clear) the type of assets")
    s.add_argument("--clear", action="store_true", help="remove the type; then every argument is an asset id")
    s.add_argument("targets", nargs="+", metavar="code_and_asset_ids", help="<code> <asset_id …> (only ids with --clear)")
    s.set_defaults(fn=cmd_asset_set_type)

    s = sub.add_parser("alarms", parents=[common], help="a point's alarm limits")
    s.add_argument("point", type=int)
    s.set_defaults(fn=cmd_alarms)
    alarm = sub.add_parser("alarm", help="set or clear a point's own limits").add_subparsers(dest="action", required=True)
    s = alarm.add_parser("set", parents=[common], help="set the point's own threshold (overrides the default)")
    s.add_argument("point", type=int)
    s.add_argument("--minor", type=float)
    s.add_argument("--major", type=float)
    s.add_argument("--key", help="value to watch (default: the point type's headline value)")
    s.add_argument("--direction", choices=["high", "low"])
    s.set_defaults(fn=cmd_alarm_set)
    s = alarm.add_parser("clear", parents=[common], help="go back to the installation default")
    s.add_argument("point", type=int)
    s.set_defaults(fn=cmd_alarm_clear)

    s = sub.add_parser("devices", parents=[common], help="MaintNode devices: state, health, channels, tunnels")
    s.set_defaults(fn=cmd_devices)
    device = sub.add_parser("device", help="one MaintNode device").add_subparsers(dest="action", required=True)
    s = device.add_parser("show", parents=[common], help="channels by group, and remote access")
    s.add_argument("device", help="name or uuid (prefix)")
    s.set_defaults(fn=cmd_device_show)
    s = device.add_parser("rename", parents=[common], help="rename a device")
    s.add_argument("device", help="name or uuid (prefix)")
    s.add_argument("name")
    s.set_defaults(fn=cmd_device_rename)
    group = sub.add_parser("group", help="a device's acquisition group").add_subparsers(dest="action", required=True)
    s = group.add_parser("set", parents=[common], help="change a group: interval=600 sample_rate=25600 …")
    s.add_argument("device", help="name or uuid (prefix)")
    s.add_argument("group", help="name or uuid (prefix)")
    s.add_argument("fields", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_group_set)

    s = sub.add_parser("tunnels", parents=[common], help="remote access to devices' sites")
    s.add_argument("--all", action="store_true", help="every installation's tunnels (staff)")
    s.set_defaults(fn=cmd_tunnels)
    tunnel = sub.add_parser("tunnel", help="open a tunnel").add_subparsers(dest="action", required=True)
    s = tunnel.add_parser("open", parents=[common], help="open an http tunnel in the browser")
    s.add_argument("tunnel", help="name or uuid (prefix)")
    s.add_argument("--all", action="store_true", help="look in every installation (staff)")
    s.set_defaults(fn=cmd_tunnel_open)
    s = tunnel.add_parser("file", parents=[common], help="save an stcp tunnel's frpc connection file (staff)")
    s.add_argument("tunnel", help="name or uuid (prefix)")
    s.add_argument("-o", "--output", help="file to write (default <device>-<tunnel>.toml)")
    s.add_argument("--all", action="store_true", help="look in every installation (staff)")
    s.set_defaults(fn=cmd_tunnel_file)

    s = sub.add_parser("sources", parents=[common], help="a point's data sources")
    s.add_argument("point", type=int)
    s.set_defaults(fn=cmd_sources)
    source = sub.add_parser("source", help="add, change or remove a data source").add_subparsers(dest="action", required=True)
    s = source.add_parser("add", parents=[common], help="source_type=maintnode device=<uuid> group_name=… mn_channel=3 sensor=accelerometer")
    s.add_argument("point", type=int)
    s.add_argument("fields", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_source_add)
    s = source.add_parser("set", parents=[common], help="change a source: sensitivity=50 …")
    s.add_argument("point", type=int)
    s.add_argument("source", help="uuid (prefix)")
    s.add_argument("fields", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_source_set)
    s = source.add_parser("delete", parents=[common], help="remove a source")
    s.add_argument("point", type=int)
    s.add_argument("source", help="uuid (prefix)")
    s.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    s.set_defaults(fn=cmd_source_delete)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args, _load())
    except MechbaseError as e:
        if isinstance(e.body, str) and "<html" in e.body.lower():
            # a proxy/error page, not the API: don't dump the HTML
            sys.exit(f"Error: {e.status} from {_load()['url']} (server unavailable or not a Mechbase API)")
        sys.exit(f"Error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
