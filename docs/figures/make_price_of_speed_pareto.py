"""Static figure for docs/RESEARCH.md (offline; not part of the game).

Level 1 "The Price of Speed": every weight setting of the calibration sweep that reached the
target, time to target against effort E = sum(dt*|u|^2), and the best trade-offs among
the tested settings (no other tested setting is both faster and cheaper). This is NOT the
true Pareto front of the controller: only a 6 x 6 grid of weights (r = 1) was tested.

Data: price_of_speed_sweep.csv, written in the course Docker image by
    python calibrate.py price_of_speed --sweep --csv /workspace/docs/figures/price_of_speed_sweep.csv
Run on the host (matplotlib is in game/requirements.txt), from the repository root:
    python docs/figures/make_price_of_speed_pareto.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
CSV, PNG = HERE / "price_of_speed_sweep.csv", HERE / "price_of_speed_pareto.png"
PAR_TIME, PAR_ENERGY = 30.0, 4.75  # ★★ and ★★★ pars (game/level_data/price_of_speed.json)
REFERENCE = (0.1, 1.0)  # the level's reference weights (q_p, q_v), r = 1

# validated categorical slots 1 and 2 (dataviz reference palette), recessive ink and grid
TESTED, BEST = "#2a78d6", "#eb6834"
INK, INK_SOFT, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"


def load() -> list[dict]:
    with CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("q_p", "q_v", "r", "time_s", "energy"):
            r[k] = float(r[k])
    return rows


def nondominated(points: list[dict]) -> list[dict]:
    """Points that no other point beats in both time and effort (ties count as not beaten)."""
    def beats(a, b):
        return (a["time_s"] <= b["time_s"] and a["energy"] <= b["energy"]
                and (a["time_s"] < b["time_s"] or a["energy"] < b["energy"]))
    return sorted((p for p in points if not any(beats(o, p) for o in points)),
                  key=lambda p: p["time_s"])


def main() -> None:
    rows = load()
    ok = [r for r in rows if r["outcome"] == "success"]
    failed = {}
    for r in rows:
        if r["outcome"] != "success":
            failed[r["outcome"]] = failed.get(r["outcome"], 0) + 1
    best = nondominated(ok)

    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SOFT, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)

    # the star pars: dashed, recessive
    ax.axvline(PAR_TIME, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.axhline(PAR_ENERGY, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(PAR_TIME + 0.15, 4.12, "★★ par: 30 s", color=INK_SOFT, fontsize=8.5, va="bottom")
    ax.text(39.4, PAR_ENERGY + 0.02, "★★★ par: E ≤ 4.75", color=INK_SOFT, fontsize=8.5,
            ha="right", va="bottom")

    # all successful settings, then the best trade-offs on top (bigger, ringed, connected)
    ax.scatter([r["time_s"] for r in ok], [r["energy"] for r in ok], s=46, color=TESTED,
               edgecolor=SURFACE, linewidth=1.5, zorder=3, label="tested setting that reached the target")
    ax.step([p["time_s"] for p in best], [p["energy"] for p in best], where="post", color=BEST,
            linewidth=2, zorder=4)
    ax.scatter([p["time_s"] for p in best], [p["energy"] for p in best], s=70, color=BEST,
               edgecolor=SURFACE, linewidth=2, zorder=5, label="best trade-off among the tested settings")
    for p in best:  # direct labels only on the highlighted points
        ref = (p["q_p"], p["q_v"]) == REFERENCE
        ax.annotate(f"$q_p$={p['q_p']:g}, $q_v$={p['q_v']:g}" + (chr(10) + "(reference)" if ref else ""),
                    (p["time_s"], p["energy"]), xytext=(-8, -24) if ref else (7, 5),
                    ha="right" if ref else "left", textcoords="offset points", fontsize=8, color=INK)

    ax.set_xlabel("time to target [s]", color=INK_SOFT, fontsize=9.5)
    ax.set_ylabel(r"effort $E = \sum \Delta t\,\|u\|^2$", color=INK_SOFT, fontsize=9.5)
    ax.set_xlim(23, 40)
    fail_text = ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(failed.items()))
    fig.suptitle("The Price of Speed: speed against effort", x=0.08, ha="left", fontsize=12,
                 color=INK, fontweight="bold")
    ax.set_title(f"{len(ok)} of {len(rows)} tested weight settings reached the target "
                 f"(failed: {fail_text}).\n$r = 1$; $q_p$ and $q_v$ on a 6 × 6 grid "
                 "(calibrate.py --sweep). Not the true Pareto front.",
                 loc="left", fontsize=8.5, color=INK_SOFT)
    leg = ax.legend(loc="upper right", fontsize=8, frameon=False, labelcolor=INK_SOFT)
    leg.set_zorder(6)
    fig.tight_layout()
    fig.savefig(PNG, facecolor=SURFACE)
    print(f"wrote {PNG} ({len(ok)} successes, {len(best)} best trade-offs: "
          + "; ".join(f"q_p={p['q_p']:g} q_v={p['q_v']:g} -> {p['time_s']:.1f} s, E={p['energy']:.2f}"
                      for p in best) + ")")


if __name__ == "__main__":
    main()
