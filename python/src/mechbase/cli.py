"""`mechbase` command line — readings, points and spectra from a terminal.

    mechbase login                      # once; stores a token in ~/.config/mechbase/config.json
    mechbase points --asset 1
    mechbase readings 2
    mechbase reading show 2 766         # values, state and the top spectrum peaks
    mechbase reading delete 2 767

Every command takes --json for scripting. MECHBASE_TOKEN / MECHBASE_URL /
MECHBASE_INSTALLATION override the stored config.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import sys
from pathlib import Path

from . import Mechbase
from ._http import HttpClient
from .errors import MechbaseError

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mechbase" / "config.json"


def _load() -> dict:
    try:
        cfg = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        cfg = {}
    for key, env in (("token", "MECHBASE_TOKEN"), ("url", "MECHBASE_URL"), ("installation", "MECHBASE_INSTALLATION")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    cfg.setdefault("url", Mechbase.DEFAULT_BASE_URL)
    return cfg


def _save(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2))
    CONFIG.chmod(0o600)


def _client(cfg: dict) -> Mechbase:
    if not cfg.get("token"):
        sys.exit("Not signed in. Run: mechbase login")
    return Mechbase(token=cfg["token"], base_url=cfg["url"])


def _inst(args, cfg, client):
    iid = args.installation or cfg.get("installation") or client.me().current_installation_id
    return client.for_installation(int(iid))


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
        tag = f"{k}×{line_hz:g} Hz (electrical)" if k and abs(f - k * line_hz) <= df else ""
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
    cfg.update(token=body["token"], url=url)
    _save(cfg)
    me = Mechbase(token=cfg["token"], base_url=url).me()
    print(f"Signed in as {me.user.email or me.user.username} on {url}")


def cmd_whoami(args, cfg):
    me = _client(cfg).me()
    current = int(cfg.get("installation") or me.current_installation_id)
    rows = [{"id": i.installation_id, "name": i.name, "current": "*" if i.installation_id == current else ""}
            for i in me.installations]
    if not args.json:
        print(f"{me.user.email or me.user.username} @ {cfg['url']}")
    _out(args, rows, ["current", "id", "name"])


def cmd_use(args, cfg):
    cfg["installation"] = args.installation_id
    _save(cfg)
    print(f"Using installation {args.installation_id}")


def cmd_assets(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    rows = [{"id": a.asset_id, "name": a.name, "status": a.status} for a in inst.assets.list(q=args.q, limit=args.limit)]
    _out(args, rows, ["id", "name", "status"])


def cmd_points(args, cfg):
    inst = _inst(args, cfg, _client(cfg))
    pts = inst.measurement_points.list(q=args.q, asset_id=args.asset, limit=args.limit)
    rows = [{"id": p.point_id, "asset": p.asset_id, "name": p.name, "type": p.transducer_type,
             "unit": p.measurement_unit_code, "status": p.status} for p in pts]
    _out(args, rows, ["id", "asset", "name", "type", "unit", "status"])


def _reading_row(m) -> dict:
    vals = ", ".join(f"{k}={v:.3g}" if isinstance(v, (int, float)) else f"{k}={v}" for k, v in m.data.items())
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
    for k, v in m.data.items():
        print(f"  {k:<14} {v}")
    if m.file_url:
        print(f"  file           {m.file_url}")
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
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args, _load())
    except MechbaseError as e:
        sys.exit(f"Error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
