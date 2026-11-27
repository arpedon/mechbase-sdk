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
    mechbase overview ; mechbase alerts ; mechbase activity ; mechbase search pump
    mechbase dashboard                  # the default board's tiles
    mechbase reading analysis 2 766     # values, peaks, bearing markers, shaft order
    mechbase runs "Daily round" ; mechbase run report <uuid> ; mechbase ncs
    mechbase device lookup <balena uuid> ; mechbase device claim <balena uuid> --name "Boiler"

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


# --- mobile-parity commands ---------------------------------------------------


def _when(ts: str | None) -> str:
    return ts[:16].replace("T", " ") if ts else ""


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _alert_rows(rows: list[dict]) -> list[dict]:
    return [{"asset": a.get("asset_id") or "", "name": a["name"], "status": "silent" if a.get("is_silent") else STATUS.get(a["status"], a["status"]),
             "reason": a.get("reason") or "", "where": " · ".join(x for x in (a.get("section_name"), a.get("zone_name")) if x),
             "since": _when(a.get("alert_since"))} for a in rows]


def cmd_overview(args, cfg):
    ov = _inst(args, cfg, _client(cfg)).overview()
    if args.json:
        return _print_json(ov)
    s = ov.get("status_summary") or {}
    print(f"{s.get('total', 0)} assets · {s.get('nominal', 0)} good · {s.get('elevated', 0)} elevated · "
          f"{s.get('warning', 0)} minor · {s.get('critical', 0)} major · {ov.get('silent_count', 0)} silent"
          + (f" · last reading {_ago(ov['last_reading_at'])}" if ov.get("last_reading_at") else ""))
    if ov.get("attention"):
        more = ov.get("attention_more_count") or 0
        print("\nNeeds attention" + (f" (+{more} more: mechbase alerts)" if more else ""))
        _out(args, _alert_rows(ov["attention"]), ["asset", "name", "status", "reason", "since"])
    if ov.get("running_executions"):
        print("\nRunning")
        _out(args, [{"route": r["route_name"], "done": f"{r['done']}/{r['total']}", "by": (r.get("executed_by") or {}).get("name", ""),
                     "started": _when(r.get("started_at")), "run": r["execution_uuid"]} for r in ov["running_executions"]],
             ["route", "done", "by", "started", "run"])
    if ov.get("back_to_normal"):
        print("\nBack to normal")
        _out(args, [{"asset": b.get("asset_id") or "", "name": b["name"], "when": _when(b.get("recovered_at"))}
                    for b in ov["back_to_normal"]], ["asset", "name", "when"])


def cmd_alerts(args, cfg):
    rows = _inst(args, cfg, _client(cfg)).alerts(silent=args.silent)
    if args.json:
        return _print_json(rows)
    if not rows:
        return print("No silent assets." if args.silent else "Nothing needs attention.")
    _out(args, _alert_rows(rows), ["asset", "name", "status", "reason", "where", "since"])


def cmd_activity(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    items = []
    for e in inst.activity.iter(section_id=args.section, page_size=min(args.limit, 200)):
        items.append(e)
        if len(items) >= args.limit:
            break
    if args.json:
        return _print_json(items)
    day = None
    for e in items:  # newest first; a header per local day
        local = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone()
        if local.date() != day:
            day = local.date()
            print(f"\n{day.isoformat()}")
        by = (e.get("actor") or {}).get("name")
        print(f"  {local:%H:%M}  {e['title']}" + (f" — {e['detail']}" if e.get("detail") else "") + (f" ({by})" if by else ""))


_SEARCH_ID = ("asset_id", "point_id", "zone_id", "section_id", "check_id", "comment_id", "uuid", "response_uuid")
_SEARCH_NAME = ("name", "label", "body_text", "notes")


def cmd_search(args, cfg):
    res = _inst(args, cfg, _client(cfg)).search(args.query, in_=args.category)
    if args.json:
        return _print_json(res)
    cats = res.get("categories") or []
    print(f"{res.get('total_count', 0)} results: " + ", ".join(f"{c['slug']} {c['count']}" for c in cats if c["count"]))
    for c in cats:
        rows = res.get(c["key"]) or []
        if not rows:
            continue
        print(f"\n{c['label']} ({c['count']})")
        for r in rows:
            rid = next((r[k] for k in _SEARCH_ID if r.get(k) is not None), "")
            name = next((r[k] for k in _SEARCH_NAME if r.get(k)), "")
            where = r.get("asset_name") or r.get("route_name") or r.get("section_name") or ""
            print(f"  {rid}  {' '.join(str(name).split())[:80]}" + (f"  · {where}" if where else ""))


def cmd_hours(args, cfg):
    h = _inst(args, cfg, _client(cfg)).hours(production_from=args.since, production_to=args.until)
    if args.json:
        return _print_json(h)
    print(f"Running hours {_when(h.get('window_start'))} → {_when(h.get('window_end'))}")
    _out(args, [{"asset": r.get("asset_id") or "", "name": r["asset_name"], "state": r.get("state") or "unknown",
                 "hours": f"{r['range_hours']:.1f}", "lifetime": f"{r['lifetime_hours']:.0f}", "last ping": _ago(r.get("last_ping"))}
                for r in h.get("rows") or []], ["asset", "name", "state", "hours", "lifetime", "last ping"])


def cmd_production_flip(args, cfg):
    st = _inst(args, cfg, _client(cfg)).assets.flip_production(args.asset)
    print(json.dumps(st) if args.json else f"Asset {args.asset} is now {st.get('state') or 'unknown'}.")


def cmd_dashboards(args, cfg):
    boards = _inst(args, cfg, _client(cfg)).dashboards.list()
    if args.json:
        return _print_json(boards)
    _out(args, [{"uuid": b.get("uuid") or "(automatic)", "name": b["name"], "default": "*" if b["is_default"] else ""}
                for b in boards], ["default", "uuid", "name"])


def cmd_dashboard(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    ref = args.dashboard
    if ref != "default":
        boards = [b for b in inst.dashboards.list() if b.get("uuid")]
        ref = _pick(boards, ref, ("uuid", "name"), "dashboard")["uuid"]
    board = inst.dashboards.get(ref).data
    if args.json:
        return _print_json(board)
    print(f"{board['name']}" + (" (automatic)" if board.get("is_automatic") else ""))
    for sec in board.get("sections") or []:
        print(f"\n{sec['title']}" + (f" · {sec['meta']}" if sec.get("meta") else "") + f" · {sec.get('status_label', '')}")
        rows = []
        for t in sec.get("tiles") or []:
            v = t.get("value")
            val = "—" if v is None else f"{v:.{t.get('decimals', 2)}f} {t.get('unit') or ''}".strip()
            rows.append({"point": t.get("point_id") or "", "tile": t["label"], "value": val,
                         "status": "STALE" if t.get("stale_since") else (t.get("status_label") or STATUS.get(t["status"], "")),
                         "state": t.get("state") or "", "measured": _ago(t.get("measured_at"))})
        _out(args, rows, ["point", "tile", "value", "status", "state", "measured"])


_SPECTRUM = {"velocity": "velocity", "acceleration": "accel", "envelope": "envelope"}


def cmd_reading_analysis(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    a = inst.measurements.analysis(args.point, args.reading, highpass_hz=args.highpass, lowpass_hz=args.lowpass)
    vib = a.get("vibration") or {}
    spec = vib.get("spectrum") or {}
    units = a.get("units") or {}
    found = peaks(spec.get("freq_hz") or [], spec.get(_SPECTRUM[args.signal]) or [], top=args.peaks, line_hz=args.line_hz)
    markers = [m for m in vib.get("bearing_markers") or [] if m.get("harmonic") == 1]
    if args.json:
        return _print_json({"point_id": a["point_id"], "point_sequence": a["point_sequence"], "status": a["status"],
                            "data": a.get("data"), "units": units, "peaks": found, "signal": args.signal,
                            "bearing_markers": markers, "order": vib.get("order"), "thermography": a.get("thermography")})
    print(f"Point {a['point_id']} · reading {a['point_sequence']} · {_when(a['created_at'])} · {a['status'].upper()} · {a.get('transducer_type', '')}")
    data = {k: v for k, v in (a.get("data") or {}).items() if isinstance(v, (int, float, str)) and not isinstance(v, bool)}
    if data:
        width = max(map(len, data))
        for k, v in data.items():
            print(f"  {k:<{width}}  {v:.4g}" if isinstance(v, float) else f"  {k:<{width}}  {v}")
    if spec.get("freq_hz"):
        print(f"\nSpectrum: {vib.get('n_lines', 0)} lines, {vib.get('freq_resolution_hz', 0):.3g} Hz/line"
              + (f", fmax {vib['fmax_hz']:g} Hz" if vib.get("fmax_hz") else "")
              + (f", envelope band {vib['env_band_hz'][0]:g}–{vib['env_band_hz'][1]:g} Hz" if vib.get("env_band_hz") else ""))
        unit = units.get("acceleration" if args.signal != "velocity" else "velocity", "")
        print(f"Top {len(found)} {args.signal} peaks ({unit}):")
        _out(args, found, ["hz", "amplitude", "note"])
    elif vib:
        print("\nNo spectrum (reading has no waveform).")
    order = vib.get("order")
    if order:
        print(f"\nShaft {order['shaft_hz']:.2f} Hz ({order['rpm']:.0f} rpm) · 1× phase {order['phase_1x']}° · 2× phase {order['phase_2x']}°")
    if markers:
        print("\nBearing markers: " + ", ".join(f"{m['label']} {m['hz']:.1f} Hz" for m in markers))
    th = a.get("thermography")
    if th and th.get("thermograms"):
        print(f"\nThermography: {len(th['thermograms'])} image(s), {th.get('hotspot_count', 0)} hot spot(s)"
              + (f", worst ΔT {th['worst_delta_t']:.1f}" if th.get("worst_delta_t") is not None else ""))
    if a.get("attachments"):
        print(f"\n{len(a['attachments'])} attachment(s)")


def _route(inst, ref: str) -> dict:
    """A route by name or uuid (prefix)."""
    if re.fullmatch(r"[0-9a-fA-F-]{36}", ref):
        return {"uuid": ref, "name": ref}
    return _pick([dataclasses.asdict(r) for r in inst.routes.list(limit=200)], ref, ("uuid", "name"), "route")


def cmd_runs(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    page = inst.routes.executions(_route(inst, args.route)["uuid"], limit=args.limit)
    if args.json:
        return _print_json(page)
    _out(args, [{"#": e["number"], "run": e["uuid"], "status": e["status"], "started": _when(e.get("started_at")),
                 "by": (e.get("executed_by") or {}).get("name", ""), "answered": e["answered_count"],
                 "passed": e["passed_count"], "ncs": e["non_conformity_count"]} for e in page["items"]],
         ["#", "run", "status", "started", "by", "answered", "passed", "ncs"])


def cmd_run_report(args, cfg):
    rep = _inst(args, cfg, _client(cfg)).routes.execution(args.run).report()
    if args.json:
        return _print_json(rep)
    ex, t = rep["execution"], rep["totals"]
    head = [rep["route"]["name"], f"run {ex['number']}", ex["status"], _when(ex.get("started_at")),
            (ex.get("executed_by") or {}).get("name")]
    print(" · ".join(h for h in head if h))
    print(f"  {t['answered']}/{t['checks']} answered · {t['passed']} passed · {t['non_conformities']} non-conformities")
    if rep.get("exceptions"):
        print("\nNon-conformities")
        _out(args, [{"check": x["name"], "status": STATUS.get(x["status"], x["status"]), "resolved": "yes" if x["resolved"] else "",
                     "response": x["response_uuid"]} for x in rep["exceptions"]], ["check", "status", "resolved", "response"])
    if rep.get("missing"):
        print("\nNot answered")
        for c in rep["missing"]:
            print(f"  #{c['check_id']} {c['label']}" + (f" · {c['asset_name']}" if c.get("asset_name") else ""))


def cmd_ncs(args, cfg):
    page = _inst(args, cfg, _client(cfg)).non_conformities.list(status=args.status, asset_id=args.asset, limit=args.limit)
    if args.json:
        return _print_json(page)
    _out(args, [{"response": n["response_uuid"], "when": _when(n["created_at"]), "route": n["route_name"], "check": n["label"],
                 "status": STATUS.get(n["status"], n["status"]), "notes": " ".join((n.get("notes") or "").split())[:60],
                 "resolved": _when(n.get("resolved_at"))} for n in page["items"]],
         ["response", "when", "route", "check", "status", "notes", "resolved"])


def cmd_nc_resolve(args, cfg):
    n = _inst(args, cfg, _client(cfg)).non_conformities.resolve(args.response, comment=args.comment)
    print(json.dumps(n, indent=2) if args.json else f"Resolved {n['label']} ({n['route_name']}).")


def cmd_survey_new(args, cfg):
    h = _inst(args, cfg, _client(cfg)).routes.start_survey(args.name)
    if args.json:
        return _print_json({"route": h.route, "execution": dataclasses.asdict(h.execution)})
    print(f"Started survey {h.route['name']} ({h.route['uuid']}): run {h.uuid}")


def cmd_route_new(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    items = [{"label": c} for c in args.check]
    if args.file:
        loaded = json.loads(Path(args.file).read_text())
        if not isinstance(loaded, list):
            sys.exit("The checks file must hold a JSON list.")
        items += loaded
    if not items:
        sys.exit("Give at least one --check or a --file of checks.")
    r = inst.routes.create(args.name, items, description=args.description)
    print(json.dumps(r, indent=2) if args.json else f"Created route {r['name']} ({r['uuid']}) with {len(r['items'])} check(s).")


def cmd_route_rename(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    r = inst.routes.update(_route(inst, args.route)["uuid"], name=args.name)
    print(json.dumps(dataclasses.asdict(r)) if args.json else f"Renamed to {r.name}.")


def cmd_route_delete(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    r = _route(inst, args.route)
    if not args.yes and input(f"Delete route {r['name']} and all its runs? It cannot be undone. [y/N] ").lower() != "y":
        sys.exit("Cancelled.")
    inst.routes.delete(r["uuid"])
    print(f"Deleted route {r['name']}.")


def _check(inst, route_uuid: str, ref: str) -> dict:
    """A route's check by its number (#), label or uuid (prefix)."""
    items = inst.routes.get(route_uuid)["items"]
    hit = [i for i in items if ref.lstrip("#").isdigit() and i["check_id"] == int(ref.lstrip("#"))]
    return hit[0] if hit else _pick(items, ref, ("uuid", "label"), "check")


def cmd_check_add(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    fields = {k: v for k, v in {"unit": args.unit, "asset_id": args.asset, "zone_id": args.zone,
                                "measurement_point_id": args.point, "subchecks": args.step or None,
                                "instructions": args.instructions}.items() if v is not None}
    c = inst.routes.add_item(_route(inst, args.route)["uuid"], args.label, item_type=args.type, **fields)
    print(json.dumps(c, indent=2) if args.json else f"Added check #{c['check_id']} {c['label']}.")


def cmd_check_rm(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    route = _route(inst, args.route)["uuid"]
    c = _check(inst, route, args.check)
    if not args.yes and input(f"Remove check #{c['check_id']} {c['label']}? [y/N] ").lower() != "y":
        sys.exit("Cancelled.")
    inst.routes.delete_item(route, c["uuid"])
    print(f"Removed check #{c['check_id']} {c['label']}.")


def cmd_check_mv(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    route = _route(inst, args.route)["uuid"]
    c = _check(inst, route, args.check)
    numbers = inst.routes.reorder_items(route, [{"uuid": c["uuid"], "position": args.position}])
    new = next((n["check_id"] for n in numbers if n["uuid"] == c["uuid"]), "?")
    print(json.dumps(numbers) if args.json else f"Moved {c['label']}: now check #{new}.")


def cmd_device_lookup(args, cfg):
    d = _inst(args, cfg, _client(cfg)).devices.lookup(args.balena_uuid)
    if args.json:
        return _print_json(d)
    say = {"claim": "free to claim: mechbase device claim " + args.balena_uuid,
           "member": f"already in this installation as {d.get('name') or d['node_uuid']}",
           "taken": f"claimed by {d.get('installation_name') or 'another installation'}",
           "not_found": "no such device", "unreachable": "the device registry did not answer; try again"}
    print(f"{args.balena_uuid}: {say.get(d['state'], d['state'])}")
    if d["state"] in ("claim", "not_found", "unreachable"):
        return
    print(f"  node {d['node_uuid']} · {'online' if d.get('is_online') else 'offline'}")


def cmd_device_claim(args, cfg):
    d = _inst(args, cfg, _client(cfg)).devices.claim(args.balena_uuid, name=args.name)
    if args.json:
        return _print_json(d)
    print(f"Claimed {d['name']} ({d['node_uuid']}). Credentials: {(d.get('token_push') or {}).get('state', '?')}; "
          f"watch it come online with: mechbase device show {d['node_uuid'][:8]}")


def cmd_device_creds(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    d = inst.devices.resend_credentials(_pick(inst.devices.list(), args.device, ("node_uuid", "name"), "device")["node_uuid"])
    print(json.dumps(d, indent=2) if args.json else f"Credentials for {d['name']}: {(d.get('token_push') or {}).get('state', '?')}.")


def cmd_device_channels(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    d = _pick(inst.devices.list(), args.device, ("node_uuid", "name"), "device")
    groups = inst.devices.channels(d["node_uuid"])
    if args.json:
        return _print_json(groups)
    for g in groups:
        used = sum(c["used"] for c in g["channels"])
        print(f"\nGroup {g['name']} ({g['hardware_type']}): {used} used" + (f" of {g['slots']}" if g.get("slots") else ""))
        _out(args, [{"channel": f"CH{c['channel']}", "point": f"{c['point_id']} {c.get('asset_name') or ''} · {c.get('point_name') or ''}" if c["used"] else "free",
                     "sensor": c.get("sensor") or "", "state": (c.get("state") or "").upper()} for c in g["channels"]],
             ["channel", "point", "sensor", "state"])


def cmd_bearing_search(args, cfg):
    res = _inst(args, cfg, _client(cfg)).bearings.search(args.query or "", order=args.order)
    if args.json:
        return _print_json(res)
    rows = res.get("results") if (args.query or args.order) else res.get("own")
    _out(args, [{"uuid": b["uuid"], "designation": b["designation"], "maker": b.get("manufacturer") or "", "source": b.get("source") or "",
                 "bpfo": b["bpfo"], "bpfi": b["bpfi"], "bsf": b["bsf"], "ftf": b["ftf"], "match": b.get("match") or ""} for b in rows or []],
         ["uuid", "designation", "maker", "source", "bpfo", "bpfi", "bsf", "ftf"] + (["match"] if args.order else []))


def cmd_finding_new(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    if not args.fault or not args.severity:
        ch = inst.findings.choices()
        print("Fault types: " + ", ".join(c["value"] for c in ch["fault_types"]))
        print("Severities:  " + ", ".join(c["value"] for c in ch["severities"]))
        sys.exit("Give --fault and --severity.")
    f = inst.findings.create(point_id=args.point, point_sequence=args.reading, fault_type=args.fault, severity=args.severity,
                             recommended_action=args.action, comment=args.comment, due_by=args.due, hz=args.hz)
    print(json.dumps(dataclasses.asdict(f), indent=2, default=str) if args.json
          else f"Recorded {f.fault_type_display or f.fault_type} ({f.severity}) on {f.asset_name} · {f.point_name}: {f.uuid}")


_NOTIFY = ("severity_threshold", "status_changes", "route_completions", "exports", "notifications_muted")


def _print_notify(args, n):
    if args.json:
        return _print_json(n)
    label = {c["value"]: c["label"] for c in n.get("threshold_choices") or []}
    print(f"severity_threshold   {n['severity_threshold']} ({label.get(n['severity_threshold'], '')})")
    for k in _NOTIFY[1:]:
        print(f"{k:<20} {'on' if n[k] else 'off'}")


def cmd_notify_show(args, cfg):
    _print_notify(args, _inst(args, cfg, _client(cfg)).notification_settings.get())


def cmd_notify_set(args, cfg):
    fields = _fields(args.fields)
    bad = set(fields) - set(_NOTIFY)
    if bad:
        sys.exit(f"Unknown setting {', '.join(sorted(bad))}; one of: {', '.join(_NOTIFY)}")
    fields = {k: {"on": True, "off": False}.get(v, v) for k, v in fields.items()}
    _print_notify(args, _inst(args, cfg, _client(cfg)).notification_settings.update(**fields))


def cmd_notify_test(args, cfg):
    result = _inst(args, cfg, _client(cfg)).notification_settings.test()
    print(json.dumps({"result": result}) if args.json else
          ("Test e-mail sent." if result == "sent" else "The server has no mail set up: the test was only logged."))


_UNITS = ("acceleration", "velocity", "temperature", "pressure", "frequency")


def cmd_me_set_units(args, cfg):
    prefs = {k: str(v) for k, v in _fields(args.units).items()}
    bad = set(prefs) - set(_UNITS)
    if bad:
        sys.exit(f"Unknown unit {', '.join(sorted(bad))}; one of: {', '.join(_UNITS)}")
    me = _client(cfg).update_me(unit_prefs=prefs)
    print(json.dumps(me.unit_prefs) if args.json else "Units: " + ", ".join(f"{k} {v}" for k, v in me.unit_prefs.items()))


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

    s = reading.add_parser("analysis", parents=[common], help="analysis summary: values, spectrum peaks, markers, order")
    s.add_argument("point", type=int)
    s.add_argument("reading", type=int, help="the number in the web URL")
    s.add_argument("--peaks", type=int, default=10, help="how many spectrum peaks")
    s.add_argument("--signal", choices=list(_SPECTRUM), default="velocity")
    s.add_argument("--highpass", type=float, help="Hz")
    s.add_argument("--lowpass", type=float, help="Hz")
    s.add_argument("--line-hz", type=float, default=50.0, help="mains frequency for the electrical tag")
    s.set_defaults(fn=cmd_reading_analysis)

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
    s = finding.add_parser("new", parents=[common], help="record a finding on a reading (no --fault: list the choices)")
    s.add_argument("point", type=int)
    s.add_argument("reading", type=int, help="the number in the web URL")
    s.add_argument("--fault", help="fault type value, e.g. bpfo")
    s.add_argument("--severity", help="e.g. minor, major")
    s.add_argument("--action", default="", help="recommended action")
    s.add_argument("--comment", default="")
    s.add_argument("--due", help="due date (YYYY-MM-DD)")
    s.add_argument("--hz", type=float, help="the spectrum line it is about")
    s.set_defaults(fn=cmd_finding_new)

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
    s = device.add_parser("lookup", parents=[common], help="what a scanned label's device is: free, ours or taken")
    s.add_argument("balena_uuid", help="from the label QR (/provision/<balena_uuid>/)")
    s.set_defaults(fn=cmd_device_lookup)
    s = device.add_parser("claim", parents=[common], help="claim a device into this installation")
    s.add_argument("balena_uuid")
    s.add_argument("--name")
    s.set_defaults(fn=cmd_device_claim)
    s = device.add_parser("channels", parents=[common], help="free and used channels by group")
    s.add_argument("device", help="name or uuid (prefix)")
    s.set_defaults(fn=cmd_device_channels)
    s = device.add_parser("creds", parents=[common], help="push the device its credentials again")
    s.add_argument("device", help="name or uuid (prefix)")
    s.set_defaults(fn=cmd_device_creds)
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

    s = sub.add_parser("overview", parents=[common], help="the home page: status counts, needs attention, running routes")
    s.set_defaults(fn=cmd_overview)
    s = sub.add_parser("alerts", parents=[common], help="every asset needing attention")
    s.add_argument("--silent", action="store_true", help="every silent asset instead")
    s.set_defaults(fn=cmd_alerts)
    s = sub.add_parser("activity", parents=[common], help="recent status changes, notes, findings, route runs")
    s.add_argument("-n", "--limit", type=int, default=30)
    s.add_argument("--section", type=int, help="section id")
    s.set_defaults(fn=cmd_activity)
    s = sub.add_parser("search", parents=[common], help="search assets, points, routes, comments, notes …")
    s.add_argument("query")
    s.add_argument("--in", dest="category", choices=["assets", "sections", "zones", "points", "routes", "items", "comments", "notes"])
    s.set_defaults(fn=cmd_search)
    s = sub.add_parser("hours", parents=[common], help="running hours of production-tracked assets (default today)")
    s.add_argument("--since", help="first day (YYYY-MM-DD)")
    s.add_argument("--until", help="last day (YYYY-MM-DD)")
    s.set_defaults(fn=cmd_hours)
    prod = sub.add_parser("production", help="production state").add_subparsers(dest="action", required=True)
    s = prod.add_parser("flip", parents=[common], help="switch an asset running ⇄ stopped now")
    s.add_argument("asset", type=int)
    s.set_defaults(fn=cmd_production_flip)

    s = sub.add_parser("dashboards", parents=[common], help="list dashboards")
    s.set_defaults(fn=cmd_dashboards)
    s = sub.add_parser("dashboard", parents=[common], help="a dashboard's tiles: latest value, status, state")
    s.add_argument("dashboard", nargs="?", default="default", help="name or uuid (prefix); default: your default board")
    s.set_defaults(fn=cmd_dashboard)

    s = sub.add_parser("runs", parents=[common], help="a route's run history")
    s.add_argument("route", help="name or uuid (prefix)")
    s.add_argument("-n", "--limit", type=int, default=20)
    s.set_defaults(fn=cmd_runs)
    run = sub.add_parser("run", help="one route run").add_subparsers(dest="action", required=True)
    s = run.add_parser("report", parents=[common], help="totals, non-conformities, unanswered checks")
    s.add_argument("run", help="run uuid (from `mechbase runs`)")
    s.set_defaults(fn=cmd_run_report)
    s = sub.add_parser("ncs", parents=[common], help="non-conformities (failed checks) to follow up")
    s.add_argument("--status", choices=["open", "resolved", "all"], default="open")
    s.add_argument("--asset", type=int)
    s.add_argument("-n", "--limit", type=int, default=50)
    s.set_defaults(fn=cmd_ncs)
    nc = sub.add_parser("nc", help="resolve a non-conformity").add_subparsers(dest="action", required=True)
    s = nc.add_parser("resolve", parents=[common], help="mark a non-conformity resolved")
    s.add_argument("response", help="uuid (from `mechbase ncs`)")
    s.add_argument("--comment", default="")
    s.set_defaults(fn=cmd_nc_resolve)
    survey = sub.add_parser("survey", help="blank surveys").add_subparsers(dest="action", required=True)
    s = survey.add_parser("new", parents=[common], help="a blank route and its first run")
    s.add_argument("name", nargs="?", default="")
    s.set_defaults(fn=cmd_survey_new)

    route = sub.add_parser("route", help="create, rename or delete a route").add_subparsers(dest="action", required=True)
    s = route.add_parser("new", parents=[common], help="a route with pass/fail checks (--check) or checks from a JSON file")
    s.add_argument("name")
    s.add_argument("--check", action="append", default=[], metavar="LABEL", help="a pass/fail check (repeat)")
    s.add_argument("--file", help="JSON list of checks ({label, item_type, unit, measurement_point_id …})")
    s.add_argument("--description", default="")
    s.set_defaults(fn=cmd_route_new)
    s = route.add_parser("rename", parents=[common], help="rename a route")
    s.add_argument("route", help="name or uuid (prefix)")
    s.add_argument("name")
    s.set_defaults(fn=cmd_route_rename)
    s = route.add_parser("delete", parents=[common], help="delete a route and its runs")
    s.add_argument("route", help="name or uuid (prefix)")
    s.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    s.set_defaults(fn=cmd_route_delete)
    check = sub.add_parser("check", help="a route's checks").add_subparsers(dest="action", required=True)
    s = check.add_parser("add", parents=[common], help="append a check to a route")
    s.add_argument("route", help="name or uuid (prefix)")
    s.add_argument("label")
    s.add_argument("--type", choices=["pass_fail", "numerical", "multi_check", "measurement"], default="pass_fail")
    s.add_argument("--unit", help="numerical checks")
    s.add_argument("--point", type=int, help="measurement checks: the point")
    s.add_argument("--asset", type=int)
    s.add_argument("--zone", type=int)
    s.add_argument("--step", action="append", help="multi_check steps (repeat)")
    s.add_argument("--instructions")
    s.set_defaults(fn=cmd_check_add)
    s = check.add_parser("rm", parents=[common], help="remove a check (archived if past runs answered it)")
    s.add_argument("route", help="name or uuid (prefix)")
    s.add_argument("check", help="check number, label or uuid (prefix)")
    s.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    s.set_defaults(fn=cmd_check_rm)
    s = check.add_parser("mv", parents=[common], help="move a check to a position within its stop")
    s.add_argument("route", help="name or uuid (prefix)")
    s.add_argument("check", help="check number, label or uuid (prefix)")
    s.add_argument("position", type=int, help="0 = first")
    s.set_defaults(fn=cmd_check_mv)

    bearing = sub.add_parser("bearing", help="bearing defect frequencies").add_subparsers(dest="action", required=True)
    s = bearing.add_parser("search", parents=[common], help="search the library (no query: this installation's own)")
    s.add_argument("query", nargs="?", help="designation or manufacturer, e.g. 6205")
    s.add_argument("--order", type=float, help="instead: bearings whose defect orders match a tone at this order of shaft speed")
    s.set_defaults(fn=cmd_bearing_search)

    notify = sub.add_parser("notify", help="your notification settings").add_subparsers(dest="action", required=True)
    s = notify.add_parser("show", parents=[common], help="what you are notified about")
    s.set_defaults(fn=cmd_notify_show)
    s = notify.add_parser("set", parents=[common], help="severity_threshold=3 status_changes=off notifications_muted=on …")
    s.add_argument("fields", nargs="+", metavar="key=value")
    s.set_defaults(fn=cmd_notify_set)
    s = notify.add_parser("test", parents=[common], help="send yourself a test e-mail")
    s.set_defaults(fn=cmd_notify_test)

    me = sub.add_parser("me", help="your account").add_subparsers(dest="action", required=True)
    s = me.add_parser("set-units", parents=[common], help="velocity=in/s acceleration=g temperature=°F …")
    s.add_argument("units", nargs="+", metavar="quantity=unit")
    s.set_defaults(fn=cmd_me_set_units)
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
