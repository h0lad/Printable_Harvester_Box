"""Steady-state thermal study of the sealed case in the sun, with a lumped model.

The model has two nodes and the solar panel. The panel is a flat plate 8 mm off the lid. It absorbs the
sun, loses part of that heat upward, and passes the rest across the gap to the lid. The part of the lid
that the panel does not cover takes the sun directly. The shell takes the sun, loses heat to the air and
to the sky, and passes the rest to the internal air, which also takes the electronics dissipation.

    T_case = T_amb + (Q_solar + P_int) / (h_out*A_sb + A_top_shaded*U_gap + h_out*A_top_bare)
    T_air  = T_case + P_int / (h_in*A_in)

U_gap = h_gap*h_out/(h_gap + h_out) describes the panel, air and case sandwich. h_out carries convection
and radiation against a sky at 20 C, and it sets the temperature of a small dark box in full sun. h_in
rises with the gradient, as h ~ dT^0.25. A fixed small h gives a 32 K rise for 1.3 W, which no
measurement of this cavity supports.

Two lumped nodes and one internal coupling constant are the whole model, so there is no CFD, no conjugate
heat transfer and no view factors. The uncertainty that matters is the fraction of the shell that sees
sun and the internal coupling, so the model sweeps both rather than assuming them. The upgrade path is
CFD or a thermocouple in the first print.

Run with: freecadcmd thermal_lumped.py     env: T_AMB, V_WIND, P_AVG, P_TX
"""
# ruff: noqa: F821, E402  (geometry comes from the macro exec'd below)

import json
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

L, W, H = (L_IN + 2 * WALL) / 1000, (W_IN + 2 * WALL) / 1000, (FLOOR + H_IN + LID_T) / 1000
A_TOP = L * W
A_SIDE = 2 * (L + W) * H
A_BOT = L * W
A_SB = A_SIDE + A_BOT  # sides and floor: exposed to the sun and to the sky
A_IN = (2 * L_IN * W_IN + 2 * (L_IN + W_IN) * H_IN) / 1e6
A_PANEL = PANEL * PANEL / 1e6
A_TOP_SHADED = min(A_PANEL, A_TOP)  # the panel shades this part of the lid
A_TOP_BARE = max(A_TOP - A_TOP_SHADED, 0.0)  # the rest of the lid takes the sun directly
V_IN_L = L_IN * W_IN * H_IN / 1e6

# The material and the environment. The report says which of these five the tool sweeps and which it
# states.
K_PA12 = 0.25  # W/m/K, SLS PA12
WALL_M = WALL / 1000
EPS = 0.9
SIGMA = 5.67e-8
SKY_C = 20.0  # effective sky temperature for the radiative term, C
H_IN_CONV = 3.0  # W/m2K internal air to wall at a 10 K rise, swept below
H_GAP = 7.0  # W/m2K across the 8 mm panel gap, open at the edges
ALPHA_PANEL = 0.60  # of the light the panel does not convert, this much ends up as heat in it
CASES = [
    ("bright nylon, diffuse light, shaded mounting", 150.0, 0.40, 1.0),
    ("bright nylon, full sun, half the shell lit", 1000.0, 0.40, 0.5),
    ("black nylon, full sun, half the shell lit", 1000.0, 0.90, 0.5),
]
T_AMB = float(os.environ.get("T_AMB", "40"))  # C, hot summer day
V_WIND = float(os.environ.get("V_WIND", "1.0"))  # m/s, still air
P_AVG = float(os.environ.get("P_AVG", "0.3"))  # W, LoRa node at a typical duty cycle
P_TX = float(os.environ.get("P_TX", "1.3"))  # W, during a transmit burst


def h_out(T_s, v):
    """Returns convection plus linearised radiation against the sky, in W/m2K."""
    T = T_s + 273.15
    T_sky = SKY_C + 273.15
    h_rad = EPS * SIGMA * (T**4 - T_sky**4) / max(T - T_sky, 1e-6)
    return 5.7 + 3.8 * v + h_rad


def solve(G, alpha_case, sun_frac, P_int, T_amb=T_AMB, v=V_WIND, h_in=H_IN_CONV):
    A_sun = sun_frac * A_SB
    T_s = T_amb
    T_air = T_amb + P_int / (h_in * A_IN)
    for _ in range(80):  # h_out depends on T_s and h_in on the rise, so iterate both
        ho = h_out(T_s, v)
        U_gap = H_GAP * ho / (H_GAP + ho)
        q_solar = A_sun * alpha_case * G + A_TOP_SHADED * H_GAP * ALPHA_PANEL * G / (H_GAP + ho)
        q_solar += A_TOP_BARE * alpha_case * G
        g_case = ho * A_SB + A_TOP_SHADED * U_gap + ho * A_TOP_BARE
        new_s = T_amb + (q_solar + P_int) / g_case
        h_eff = h_in * max(1.0, (max(T_air - new_s, 0.0) / 10.0) ** 0.25)
        new_air = new_s + P_int / (h_eff * A_IN)
        if abs(new_s - T_s) < 1e-7 and abs(new_air - T_air) < 1e-7:
            T_s, T_air = new_s, new_air
            break
        T_s, T_air = new_s, new_air
    ho = h_out(T_s, v)
    T_panel = (ALPHA_PANEL * G + H_GAP * T_s + ho * T_amb) / (H_GAP + ho)
    return {
        "case": T_s,
        "air": T_air,
        "panel": T_panel,
        "q_solar": q_solar,
        "q_int": P_int,
        "h_out": ho,
        "h_in_eff": h_in * max(1.0, (max(T_air - T_s, 0.0) / 10.0) ** 0.25),
    }


print(
    f"case {L * 1000:.1f} x {W * 1000:.1f} x {H * 1000:.1f} mm, shell {A_SB:.4f} m2, top {A_TOP:.4f} m2 "
    f"({A_TOP_SHADED:.4f} shaded by the panel, {A_TOP_BARE:.4f} bare), inner {A_IN:.4f} m2, "
    f"cavity {V_IN_L * 1000:.0f} ml"
)
print(f"panel {PANEL:.0f} x {PANEL:.0f} = {A_PANEL:.4f} m2 over a {STANDOFF_H:.0f} mm gap, {WALL:.1f} mm wall")
print(f"ambient {T_AMB:.0f} C, wind {V_WIND:.1f} m/s, PA12 k {K_PA12} W/m/K\n")
print(f"{'case':48} {'T air':>7} {'T case':>7} {'T panel':>8} {'Q solar':>8}  verdict")
print("-" * 100)
out = []
bad = 0
for name, G, alpha, sun in CASES:
    for tag, P in (("average duty", P_AVG), (f"{P_TX} W transmit, fault case", P_TX)):
        r = solve(G, alpha, sun, P)
        hot_lipo = r["air"] > 45.0
        hot_elec = r["air"] > 85.0
        bad += 1 if hot_lipo else 0
        verdict = "ELECTRONICS OVER 85 C" if hot_elec else ("LiPo over 45 C" if hot_lipo else "within 0-45 C")
        print(
            f"{name + ', ' + tag:48} {r['air']:6.1f}C {r['case']:6.1f}C {r['panel']:7.1f}C "
            f"{r['q_solar']:7.2f}W  {verdict}"
        )
        out.append(
            {
                "scenario": name,
                "duty": tag,
                "G_w_m2": G,
                "alpha_case": alpha,
                "sun_fraction": sun,
                "P_int_w": P,
                **r,
                "lipo_ok": not hot_lipo,
                "electronics_ok": not hot_elec,
            }
        )

M_BOARD = pcb.Volume / 1000 * 1.85 * 1.5  # cm3 of FR4 at 1.85 g/cm3 and 1.5 J/g/K
M_AIR = V_IN_L * 1.2 * 1005  # m3 of air at 1.2 kg/m3 and 1005 J/kg/K
print(
    f"\na 1 s transmit burst puts {P_TX:.1f} J into {M_BOARD + M_AIR:.1f} J/K of board, battery and air: "
    f"+{P_TX / (M_BOARD + M_AIR):.2f} K. The average column in the table is the steady state."
)

print("\nsensitivity, bright nylon in full sun, average duty:")
print(f"{'what':44} {'T air':>7}  note")
print("-" * 92)
for label, kw in (
    ("sun on 30 % of the shell instead of 50 %", {"sun_frac": 0.30}),
    ("sun on 70 % of the shell instead of 50 %", {"sun_frac": 0.70}),
    ("ambient 25 C instead of 40 C", {"T_amb": 25.0}),
    ("ambient 50 C instead of 40 C", {"T_amb": 50.0}),
    ("10 m/s wind instead of 1 m/s", {"v": 10.0}),
    ("internal coupling 1 W/m2K instead of 3", {"h_in": 1.0}),
    ("internal coupling 10 W/m2K instead of 3", {"h_in": 10.0}),
    ("white paint, alpha 0.2 instead of 0.4", None),
):
    if kw is None:
        r = solve(1000.0, 0.20, 0.50, P_AVG)
    else:
        r = solve(1000.0, 0.40, kw.pop("sun_frac", 0.50), P_AVG, **kw)
    print(f"{label:44} {r['air']:6.1f}C  {'over 45 C' if r['air'] > 45 else 'ok'}")

print("\nambient sweep, bright nylon, average duty. The README states the 0-45 C LiPo corridor:")
print(f"{'ambient':>9} {'diffuse light':>14} {'full sun':>10}")
close_at = None
for ta in (20.0, 25.0, 30.0, 35.0, 40.0, 45.0):
    d = solve(150.0, 0.40, 1.0, P_AVG, T_amb=ta)["air"]
    s = solve(1000.0, 0.40, 0.5, P_AVG, T_amb=ta)["air"]
    if s > 45.0 and close_at is None:
        close_at = ta
    print(f"{ta:8.0f}C {d:13.1f}C{s:9.1f}C" + ("   <- full sun closes the corridor" if s > 45.0 else ""))

need = P_AVG / 5.0  # W/K wanted at a 5 K rise
mdot = need / 1005.0
q_m3_h = mdot / 1.2 * 3600
ach = q_m3_h / (V_IN_L / 1000.0)
print(
    f"\nthe vent: removing {P_AVG} W at a 5 K rise needs {mdot * 1e6:.0f} mg/s = {q_m3_h * 1000:.1f} l/h "
    f"through the plug, which is {ach:.0f} air changes per hour of a {V_IN_L * 1000:.0f} ml cavity. An M12 "
    "ePTFE plug breathes about a millilitre per thermal cycle, so it equalises pressure and moisture and "
    "carries no useful heat: all of it leaves through the wall."
)
wall = WALL_M / (K_PA12 * A_IN)
print(
    f"\nwall resistance alone {wall:.2f} K/W. At {P_AVG} W that is {P_AVG * wall:.1f} K from wall to "
    "internal air. Everything else is the outside film and the sun."
)


def limit_ambient(P_int, G=1000.0, alpha=0.40, sun=0.5, lo=0.0, hi=60.0):
    """Returns the ambient at which the internal air reaches the top of the LiPo corridor."""
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if solve(G, alpha, sun, P_int, T_amb=mid)["air"] > 45.0:
            hi = mid
        else:
            lo = mid
    return lo


def limit_power(T_amb, G=1000.0, alpha=0.40, sun=0.5, lo=0.0, hi=5.0):
    """Returns the average dissipation that holds the corridor at this ambient."""
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if solve(G, alpha, sun, mid, T_amb=T_amb)["air"] > 45.0:
            hi = mid
        else:
            lo = mid
    return lo


print("\noperating envelope for the 0-45 C LiPo corridor, bright nylon:")
print(f"{'mounting':32} {'ambient limit at 0.1 W':>23} {'at 0.3 W':>10} {'at 1.0 W':>10}")
envelope = []
for name, G, sun in (("shaded, diffuse light", 150.0, 1.0), ("full sun, half the shell lit", 1000.0, 0.5)):
    row = [round(limit_ambient(P, G=G, sun=sun), 1) for P in (0.1, 0.3, 1.0)]
    envelope.append({"mounting": name, "ambient_limit_c_at_w": {"0.1": row[0], "0.3": row[1], "1.0": row[2]}})
    print(f"{name:32} {row[0]:22.1f} C {row[1]:8.1f} C {row[2]:8.1f} C")
print(
    f"{'white shell, full sun':32} "
    f"{limit_ambient(0.1, alpha=0.20):22.1f} C {limit_ambient(0.3, alpha=0.20):8.1f} C "
    f"{limit_ambient(1.0, alpha=0.20):8.1f} C"
)
print("  a shaded 0.3 W node therefore holds the corridor up to a 33 C ambient and no further, and full")
print("  sun closes it at 25 C whatever the shell. Geometry cannot move this: the sun sets the case")
print("  temperature, so the fix is a shade, a white shell or a charge cut-off at 45 C.")
print("\nmaximum average dissipation that still holds the corridor:")
print(f"{'ambient':>9} {'shaded':>10} {'full sun':>10}")
for ta in (20.0, 25.0, 30.0, 35.0, 40.0):
    d_ = limit_power(ta, G=150.0, sun=1.0)
    s_ = limit_power(ta, G=1000.0, sun=0.5)
    print(f"{ta:8.0f}C {d_:9.2f} W{s_:9.2f} W")
    envelope.append({"ambient_c": ta, "max_power_shaded_w": round(d_, 2), "max_power_full_sun_w": round(s_, 2)})

json.dump(
    {
        "tool": "thermal_lumped.py",
        "model": "steady state, two nodes plus the panel, no CFD",
        "geometry": {
            "outer_mm": [L * 1000, W * 1000, H * 1000],
            "shell_m2": A_SB,
            "top_m2": A_TOP,
            "top_shaded_m2": A_TOP_SHADED,
            "top_bare_m2": A_TOP_BARE,
            "inner_m2": A_IN,
            "cavity_ml": V_IN_L * 1000,
            "panel_m2": A_PANEL,
        },
        "limits": {"electronics_max_c": 85.0, "lipo_corridor_c": [0.0, 45.0]},
        "assumptions_not_in_the_repo": [
            "electronics dissipation 0.3 W average, 1.3 W transmit",
            "sun fraction on the shell 0.5 in full sun",
            "internal coupling 3 W/m2K at a 10 K rise",
            "sky temperature 20 C, emissivity 0.9",
        ],
        "scenarios": out,
        "scenarios_over_lipo_corridor": bad,
        "ambient_where_full_sun_closes_corridor_c": close_at,
        "board_battery_air_j_per_k": M_BOARD + M_AIR,
        "tx_burst_rise_k_per_s": P_TX / (M_BOARD + M_AIR),
        "wall_resistance_k_per_w": wall,
        "vent_air_changes_per_hour_for_0.3_w_at_5_k": ach,
        "corridor_envelope": envelope,
        "verdict": "no passive shell holds 0-45 C at a 40 C ambient in the sun. At 0.3 W the corridor "
        "closes at a 25 C ambient in full sun and at 33 C shaded. The mitigation is a shade, a shell "
        "with alpha under 0.3, or a charge cut-off at 45 C, and it belongs in the deployment, not in "
        "the wall thickness",
    },
    open(os.path.join(HERE, "thermal_report.json"), "w"),
    indent=1,
)
print("\nwrote thermal_report.json")
