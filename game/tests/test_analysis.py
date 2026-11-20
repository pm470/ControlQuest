"""Tests of the Analysis tab's plot data and AnalysisPanel (no engine needed).

Run from game/:   python -m unittest discover -s tests -v
(Qt runs offscreen; the trajectories are small synthetic ones in the engine's JSON format.)
"""

from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from controlquest.engine.protocol import RunResult  # noqa: E402
from controlquest.gameplay.analysis_panel import (AnalysisPanel, PlotSpec, Series,  # noqa: E402
                                                  render_plot)
from controlquest.gameplay.level_data import load_level_data  # noqa: E402
from controlquest.levels.level_0_hello_mpc import HelloMpcWidget  # noqa: E402
from controlquest.levels.level_1_price_of_speed import PriceOfSpeedWidget  # noqa: E402
from controlquest.levels.level_2_brake_check import BrakeCheckWidget  # noqa: E402
from controlquest.levels.level_3_dead_end import DeadEndWidget  # noqa: E402
from controlquest.levels.level_4_crosswind import (crosswind_plots, prediction_segments,  # noqa: E402
                                                   wind_bound)

APP = QApplication.instance() or QApplication(["test"])
DT = 0.1


def result(level_id, xs, us=None, energy=None, **traj) -> RunResult:
    """A RunResult with n+1 states xs (each [px, py, vx, vy]) at t_k = k dt."""
    n = len(xs) - 1
    payload = {
        "level_id": level_id, "outcome": traj.pop("outcome", "success"), "stars": 1, "metrics": {},
        "messages": [], "knobs": {}, "waypoints": traj.pop("waypoints", []),
        "trajectory": {"dt": DT, "t": [k * DT for k in range(n + 1)], "x": xs,
                       "u": us or [[0.0, 0.0]] * n, "plans": traj.pop("plans", [[x] for x in xs[:n]]),
                       "energy": energy or [0.0] * (n + 1), **traj},
    }
    return RunResult.from_json(payload)


def plots_of(widget_cls, level_id, res):
    """A level's analysis_plots without building the whole play screen (it only uses .data)."""
    return widget_cls.analysis_plots(SimpleNamespace(data=load_level_data(level_id)), res)


class LevelPlotData(unittest.TestCase):
    def test_speed_and_distance(self):
        xs = [[3.0, 8.0, 0.0, 0.0], [3.1, 8.0, 1.0, 0.0], [4.0, 9.0, 3.0, 4.0]]
        p_speed, p_dist = plots_of(HelloMpcWidget, "hello_mpc", result("hello_mpc", xs))
        self.assertEqual(list(p_speed.series[0].y), [0.0, 1.0, 5.0])
        self.assertEqual(list(p_speed.series[0].t), [0.0, DT, 2 * DT])
        target = load_level_data("hello_mpc").target
        self.assertAlmostEqual(p_dist.series[0].y[2], math.hypot(4.0 - target[0], 9.0 - target[1]))

    def test_effort_uses_the_trajectory_and_the_level_file(self):
        xs = [[5.0, 25.0, 0.0, 0.0]] * 3
        res = result("price_of_speed", xs, energy=[0.0, 0.4, 0.8])
        _speed, effort = plots_of(PriceOfSpeedWidget, "price_of_speed", res)
        self.assertEqual(list(effort.series[0].y), [0.0, 0.4, 0.8])
        d = load_level_data("price_of_speed")
        self.assertEqual([r.y for r in effort.ref_lines], [d.budget["energy"], d.pars["energy"]])
        self.assertIn("m$^2$/s$^3$", effort.y_label)
        self.assertNotIn("energy [J]", effort.y_label)

    def test_brake_check_stopping_distance_and_shading(self):
        d = load_level_data("brake_check")
        x_wall, a = d.workspace[1][0], d.a_max
        xs = [[40.0, 25.0, 4.0, 0.0], [43.0, 25.0, 4.0, 0.0], [44.0, 25.0, -1.0, 0.0]]
        vx_plot, dist = plots_of(BrakeCheckWidget, "brake_check", result("brake_check", xs))
        self.assertEqual(list(vx_plot.series[0].y), [4.0, 4.0, -1.0])
        self.assertEqual(vx_plot.ref_lines[0].y, d.v_max)
        d_wall, d_stop = (list(s.y) for s in dist.series)
        self.assertEqual(d_wall, [x_wall - 40.0, x_wall - 43.0, x_wall - 44.0])
        self.assertEqual(d_stop, [16 / (2 * a), 16 / (2 * a), 0.0])  # max(v_x, 0)^2 / (2 a_max)
        self.assertEqual(list(dist.shades[0].mask), [s > w for s, w in zip(d_stop, d_wall)])

    def test_dead_end_distance_to_final_target_and_switch_times(self):
        target = load_level_data("dead_end").target
        xs = [[5.0, 25.0, 0, 0], [6.0, 26.0, 1, 1], [7.0, 27.0, 1, 1], [8.0, 28.0, 1, 1], [9.0, 29.0, 1, 1]]
        res = result("dead_end", xs, ref_index=[0, 0, 1, 1], waypoints=[[10.0, 40.0]])
        dist, speed = plots_of(DeadEndWidget, "dead_end", res)
        self.assertAlmostEqual(dist.series[0].y[3], math.hypot(8.0 - target[0], 28.0 - target[1]))
        self.assertEqual([list(e.times) for e in speed.events], [[2 * DT]])  # first solve with ref 1
        no_wp = result("dead_end", xs, ref_index=[0, 0, 0, 0])
        self.assertEqual(plots_of(DeadEndWidget, "dead_end", no_wp)[1].events, ())
        self.assertIn("stationary point", dist.description)
        self.assertNotIn("local minimum", dist.description + speed.description)


class CrosswindPredictionError(unittest.TestCase):
    def setUp(self):
        self.d = load_level_data("crosswind")

    def test_wind_bound_from_the_level_file(self):
        w = self.d.raw["wind"]
        expected = math.hypot(*(abs(c) + abs(a) for c, a in zip(w["constant"], w["gust_amplitude"])))
        self.assertAlmostEqual(wind_bound(self.d), expected)

    def test_segments_use_the_outgoing_plan_and_skip_t0(self):
        n, steps = 8, [0, 3, 6]  # re-plans at samples 3 and 6
        drift = [0.0] + [0.01 * k for k in range(1, n + 1)]
        tr = result("crosswind", [[0, 0, 0, 0]] * (n + 1), drift=drift, solve_steps=steps,
                    plans=[[[0, 0, 0, 0]] * 31] * 3).trajectory
        t, err, bound = prediction_segments(tr, 0.9)
        nan = [i for i, v in enumerate(t) if isinstance(v, float) and math.isnan(v)]
        self.assertEqual(len(nan), 3)  # one break after each plan's segment
        samples = [round(v / DT) for v in t if not math.isnan(v)]
        self.assertEqual(samples, [1, 2, 3, 4, 5, 6, 7, 8])  # t = 0 left out
        taus = [round((2 * b / 0.9) ** 0.5 / DT) for b in bound if not math.isnan(b)]
        self.assertEqual(taus, [1, 2, 3, 1, 2, 3, 1, 2])  # at samples 3 and 6: tau = whole stretch
        self.assertEqual([e for e in err if not math.isnan(e)], drift[1:])  # engine values, unchanged

    def test_every_sample_replanned(self):
        n = 5
        tr = result("crosswind", [[0, 0, 0, 0]] * (n + 1), drift=[0.0] + [0.004] * n,
                    solve_steps=list(range(n)), plans=[[[0, 0, 0, 0]] * 31] * n).trajectory
        t, _err, bound = prediction_segments(tr, 0.9)
        self.assertTrue(all(math.isclose(b, 0.5 * 0.9 * DT**2) for b in bound if not math.isnan(b)))

    def test_solve_staircase_and_reference_lines(self):
        n, steps = 6, [0, 2, 4]
        res = result("crosswind", [[0, 0, 0, 0]] * (n + 1), drift=[0.0] * (n + 1), solve_steps=steps,
                     plans=[[[0, 0, 0, 0]] * 31] * 3, solve_budget=60)
        _err_plot, solves = crosswind_plots(res, self.d)
        s = solves.series[0]
        self.assertEqual((s.style, list(s.y)), ("step", [1, 2, 3, 3]))
        for got, want in zip(s.t, [0.0, 0.2, 0.4, 0.6]):  # solve times, then the run's end
            self.assertAlmostEqual(got, want)
        self.assertEqual([r.y for r in solves.ref_lines], [60, self.d.pars["solves"]])


class Panel(unittest.TestCase):
    SPEC = PlotSpec(title="T", description="D", y_label="y [m]", t_end=2.0,
                    series=(Series([0.0, 1.0, 2.0], [0.0, 1.0, 0.5]),))

    def test_render_size_and_axes(self):
        r = render_plot(self.SPEC, 400, 200, 1.75)
        self.assertEqual((r.image.width(), r.image.height()), (700, 350))  # device pixels
        left, right, top, bottom = r.axes
        self.assertTrue(0 < left < right <= 400 and 0 <= top < bottom <= 200)
        self.assertEqual(r.xlim, (0.0, 2.0))

    def test_panel_states_and_cursor_without_rerender(self):
        panel = AnalysisPanel()
        panel.resize(500, 600)
        panel.show()
        self.assertFalse(panel.has_plots())
        panel.set_plots([self.SPEC, self.SPEC])
        for _ in range(5):
            APP.processEvents()
        self.assertEqual(len(panel.views), 2)
        view = panel.views[0]
        view._render()  # what the timer does
        renders = view.renders
        panel.set_time(0.0)
        x0 = view.cursor_x()
        panel.set_time(2.0)
        x1 = view.cursor_x()
        panel.set_time(1.0)
        self.assertAlmostEqual(view.cursor_x(), (x0 + x1) / 2, places=6)  # linear in time
        self.assertEqual(view.renders, renders)  # moving the cursor never re-renders
        panel.clear()
        self.assertFalse(panel.has_plots())
        self.assertEqual(panel.views, [])
        panel.close()


if __name__ == "__main__":
    unittest.main()
