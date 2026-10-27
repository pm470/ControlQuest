"""Check and tune a level without the game (PRD 11). Run inside the container:

    python calibrate.py price_of_speed            # checks from the level file
    python calibrate.py price_of_speed --sweep    # table of time / energy over the weights
    python calibrate.py price_of_speed q_p=0.3 r=1   # one run with these knobs
    python calibrate.py dead_end fix=waypoints wp=35,40   # one run with a fix and waypoints
    python calibrate.py dead_end fix=horizon N=100

Checks: the default knobs fail with checks.default_outcome, the reference knobs
pass with checks.reference.stars, and every knob range follows the team rule
max <= max(50, 3 * reference value) (and the default/reference lie inside the range).
Exit code 1 if a check fails.
"""

from __future__ import annotations

import argparse
import sys

import runner
from level_rules.common import load_level


def show(label: str, result: dict) -> None:
    m = result["metrics"]
    print(f"{label:<10} {result['outcome']:<18} {result['stars']} stars  t={m['time']:5.1f} s  "
          f"E={m['energy']:5.2f}  max|a|={m['max_accel']:.2f}  knobs={result['knobs']}"
          + (f"  waypoints={result['waypoints']}" if result.get("waypoints") else "")
          + (f"  fix={result['fix']}  mean solve {m['mean_solve_ms']:.2f} ms" if result.get("fix") else ""))
    for msg in result["messages"]:
        print(f"{'':<10} - {msg}")


KNOB_MAX_FLOOR, KNOB_MAX_FACTOR = 50.0, 3.0  # team rule for slider ranges (AGENTS.md)


def check_knob_ranges(level: dict) -> bool:
    ref = level.get("checks", {}).get("reference", {}).get("knobs", {})
    ok = True
    for spec in level["knobs"]:
        name = spec["name"]
        if "choices" in spec or spec.get("scale") == "int":  # e.g. horizon N: not a weight, rule n/a
            continue
        allowed = max(KNOB_MAX_FLOOR, KNOB_MAX_FACTOR * ref.get(name, 0.0))
        if spec["max"] > allowed + 1e-12:
            print(f"FAIL: knob {name} max {spec['max']:g} > allowed {allowed:g} "
                  f"(max(50, 3 x reference {ref.get(name, 'n/a')}))")
            ok = False
        for what, value in (("default", spec["default"]), ("reference", ref.get(name))):
            if value is not None and not spec["min"] <= value <= spec["max"]:
                print(f"FAIL: knob {name} {what} {value:g} outside [{spec['min']:g}, {spec['max']:g}]")
                ok = False
    if ok:
        print(f"knob ranges ok (max <= max(50, 3 x reference))")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("level_id")
    parser.add_argument("knobs", nargs="*", help="name=value pairs (wp=x,y for a waypoint) for one run")
    parser.add_argument("--sweep", action="store_true")
    args = parser.parse_args()
    level = load_level(args.level_id)

    if args.knobs:
        pairs = [kv.split("=", 1) for kv in args.knobs]
        knobs = {k: float(v) for k, v in pairs if k not in ("wp", "fix")}
        wps = [[float(c) for c in v.split(",")] for k, v in pairs if k == "wp"]
        fix = next((v for k, v in pairs if k == "fix"), None)
        show("run", runner.run_level(args.level_id, knobs, wps or None, fix))
        return 0

    if args.sweep:
        if args.level_id != "price_of_speed":
            print("--sweep is only written for price_of_speed")
            return 1
        print("q_p / r rows, q_v columns: time [s] / energy (T/O = time out, BAT = battery empty)")
        qps, qvs = [10, 1, 0.3, 0.1, 0.03, 0.01], [0.01, 0.1, 1, 3, 10, 30]
        print(f"{'q_p':>8} " + "".join(f"{f'q_v={v:g}':>15}" for v in qvs))
        for qp in qps:
            cells = []
            for qv in qvs:
                res = runner.run_level(args.level_id, {"q_p": qp, "q_v": qv, "r": 1.0})
                tag = {"success": f"{res['metrics']['time']:.1f}", "time_out": "T/O",
                       "battery_empty": "BAT"}.get(res["outcome"], res["outcome"][:4])
                cells.append(f"{tag}/{res['metrics']['energy']:.2f}{'*' * res['stars']}")
            print(f"{qp:>8g} " + "".join(f"{c:>15}" for c in cells))
        return 0

    checks, ok = level.get("checks", {}), True
    ok = check_knob_ranges(level) and ok
    default = runner.run_level(args.level_id, {})
    show("default", default)
    expected = checks.get("default_outcome")
    if expected and default["outcome"] != expected:
        print(f"FAIL: default should end with '{expected}'")
        ok = False
    ref = checks.get("reference")
    if ref:
        res = runner.run_level(args.level_id, ref["knobs"], ref.get("waypoints"), ref.get("fix"))
        show("reference", res)
        if res["outcome"] != "success" or res["stars"] < ref.get("stars", 1):
            print(f"FAIL: reference should pass with {ref.get('stars', 1)} stars")
            ok = False
    for fix, chk in checks.get("fixes", {}).items():  # expected outcome per fix (Level 3)
        res = runner.run_level(args.level_id, chk.get("knobs", {}), chk.get("waypoints"), fix)
        show(fix, res)
        if res["outcome"] != chk["outcome"]:
            print(f"FAIL: fix {fix} should end with '{chk['outcome']}'")
            ok = False
    print("all checks passed" if ok else "checks FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
