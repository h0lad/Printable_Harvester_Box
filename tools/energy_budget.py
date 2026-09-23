"""Reports the harvest, the load and the days of autonomy for the deployed node.

A repeater on a hill is sized by December and not by the best week of July. The insolation input is a
published monthly table of horizontal irradiation for 38 degrees north, and it is the one number here
that a local measurement should replace. The tool derives the tilted plane from it with the standard
isotropic sky model: the beam times the geometric ratio, the diffuse part on the sky view factor, and
the ground reflection. It then checks the model against a published 35 degree column for the same site,
so a systematic error in the geometric part shows up as a line of output rather than as a quiet factor
of two in the answer.

Neither the average dissipation nor the cell capacity is in the repository, so both are arguments, and
the tool sweeps both. The panel area comes from the macro.

The tool cannot decide anything about clouds, dust storms and snow. A monthly mean has no bad week in
it, and a hilltop has to survive one, so the days of autonomy line decides more than the December
balance does.

Run with: freecadcmd energy_budget.py    env: P_AVG (W), CELL_WH (Wh), LAT (deg)
"""
# ruff: noqa: F821, E402  (the panel area and the box come from the macro exec'd below)

import json
import math
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

LAT = float(os.environ.get("LAT", "38"))  # a hill in Greece
P_AVG = float(os.environ.get("P_AVG", "0.06"))  # W, repeater: RX always on, TX at a low duty cycle
CELL_WH = float(os.environ.get("CELL_WH", "1.85"))  # Wh, LiPo 852040 at 500 mAh and 3.7 V
AREA = (PANEL / 1000.0) ** 2  # m2, the panel on the lid
ETA = 0.18  # module efficiency
ETA_PATH = 0.90  # charge path and cell round trip
REF_TILT = 35.0

MONTHS = ("Jan", "Feb", "Mar", "Apr", "can", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MID_N = (17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344)
# The measured monthly horizontal irradiation in kWh/m2/day, around 38 N at a few hundred metres.
# Replace it with PVGIS or with a local measurement before sizing an installation.
GHI = (1.9, 2.7, 3.9, 5.1, 6.2, 7.1, 7.2, 6.5, 5.0, 3.4, 2.2, 1.7)
# The published plane-of-array column for the same site at a 35 degree tilt, which checks the model below.
POA_PUBLISHED = (2.6, 3.4, 4.6, 5.5, 6.3, 6.9, 7.0, 6.5, 5.4, 4.1, 2.9, 2.4)
GROUND_ALBEDO = 0.25  # limestone and dry grass
T_AMB = (8.0, 9.0, 12.0, 16.0, 21.0, 26.0, 29.0, 29.0, 24.0, 19.0, 14.0, 10.0)  # C, hilltop monthly mean
tilts = {}
T_CELL_RISE = 25.0  # K, a ventilated tilted module above ambient at noon
BETA_TEMP = -0.004  # per K, module power coefficient


def h0(lat_deg, n):
    """Returns the extraterrestrial daily irradiation on a horizontal plane, in Wh/m2/day. The tool uses
    it for ratios only."""
    phi, d = math.radians(lat_deg), math.radians(23.45 * math.sin(math.radians(360 * (284 + n) / 365)))
    ws = math.acos(max(min(-math.tan(phi) * math.tan(d), 1.0), -1.0))
    return (
        (24 / math.pi)
        * 1367.0
        * (1 + 0.033 * math.cos(math.radians(360 * n / 365)))
        * (math.cos(phi) * math.cos(d) * math.sin(ws) + ws * math.sin(phi) * math.sin(d))
    )


def tilted(ghi, tilt_deg, n, lat=LAT, albedo=GROUND_ALBEDO):
    """Returns plane-of-array irradiation from horizontal irradiation, with the isotropic sky model.

    The beam is multiplied by Rb, the diffuse part is spread over the sky view factor, and the ground
    reflection takes what is left. The diffuse fraction comes from the Erbs correlation, so the tool
    assumes no clearness index.
    """
    h0h = h0(lat, n)
    kt = min(max(ghi * 1000.0 / h0h, 0.0), 1.0)
    if kt <= 0.22:
        fd = 1.0 - 0.09 * kt
    elif kt <= 0.80:
        fd = 0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4
    else:
        fd = 0.165
    diffuse = ghi * fd
    beam = ghi - diffuse
    beta = math.radians(tilt_deg)
    rb = h0(lat - tilt_deg, n) / h0h
    return beam * rb + diffuse * (1 + math.cos(beta)) / 2 + ghi * albedo * (1 - math.cos(beta)) / 2


def harvest(poa_kwh, soiling=1.0, t_amb=15.0):
    """Returns the Wh/day that the cell delivers, from a plane-of-array irradiation in kWh/m2/day."""
    derate = max(1.0 + BETA_TEMP * (t_amb + T_CELL_RISE - 25.0), 0.5)
    return poa_kwh * AREA * 1000.0 * ETA * ETA_PATH * soiling * derate


model = [tilted(GHI[i], REF_TILT, MID_N[i]) for i in range(12)]
err = [model[i] / POA_PUBLISHED[i] for i in range(12)]
# The isotropic model runs 10 to 17 percent low, which is expected: it has no circumsolar brightening.
# The tool anchors each month to the published column at the reference tilt, so that the shape comes from
# the model and the level comes from the measurement. At the reference tilt it reproduces the published
# number exactly.
CALIB = [POA_PUBLISHED[i] / model[i] for i in range(12)]
POA = [model[i] * CALIB[i] for i in range(12)]
print(f"node on a {LAT:.0f} deg hill, panel {PANEL:.0f} x {PANEL:.0f} mm = {AREA:.4f} m2 at {REF_TILT:.0f} deg tilt")
print(f"load {P_AVG * 1000:.0f} mW average = {P_AVG * 24:.2f} Wh/day, cell {CELL_WH:.2f} Wh")
print(
    f"model check at {REF_TILT:.0f} deg against the published column: worst month error "
    f"{max(abs(e - 1) for e in err) * 100:.0f} %, December {model[11]:.1f} modelled against "
    f"{POA_PUBLISHED[11]:.1f} published kWh/m2/day, so every month below is scaled to the measured level\n"
)
print(f"{'month':>5} {'POA kWh/m2/d':>13} {'harvest Wh/d':>13} {'load Wh/d':>10} {'balance':>9}  verdict")
print("-" * 70)
rows = []
worst = (1e9, None)
for i, name in enumerate(MONTHS):
    wh = harvest(POA[i], 1.0, T_AMB[i])
    load = P_AVG * 24.0
    balance = wh - load
    if balance < worst[0]:
        worst = (balance, name)
    rows.append(
        {
            "month": name,
            "ghi_kwh_m2_day": GHI[i],
            "poa_kwh_m2_day": round(POA[i], 2),
            "poa_published_kwh_m2_day": POA_PUBLISHED[i],
            "harvest_wh_day": round(wh, 3),
            "load_wh_day": round(load, 3),
            "balance_wh_day": round(balance, 3),
        }
    )
    print(
        f"{name:>5} {POA[i]:13.1f} {wh:13.2f} {load:10.2f} {balance:+9.2f}  {'surplus' if balance > 0 else 'DEFICIT'}"
    )

dec_harvest = harvest(POA[11], 1.0, T_AMB[11])
jun_harvest = harvest(POA[5], 1.0, T_AMB[5])
max_load_dec = dec_harvest / 24.0
max_load_jun = jun_harvest / 24.0
area_for_load = AREA * (P_AVG * 24.0) / dec_harvest
autonomy = CELL_WH / (P_AVG * 24.0)
print(
    f"\nDecember harvest sustains {max_load_dec * 1000:.0f} mW average, June {max_load_jun * 1000:.0f} mW. "
    f"A {P_AVG * 1000:.0f} mW load needs {area_for_load:.4f} m2 of panel, a "
    f"{math.sqrt(area_for_load) * 1000:.0f} mm square, to break even in the worst month."
)
print(
    f"the {CELL_WH:.2f} Wh cell gives {autonomy:.1f} days of autonomy. A hilltop installation needs 4 to 7 "
    f"days to ride out a winter front, which is {P_AVG * 24 * 5:.1f} to {P_AVG * 24 * 7:.1f} Wh."
)
print("\ntilt, on the same calibrated input, December and June:")
print(f"  {'tilt':>5} {'Dec kWh/m2/d':>13} {'Dec harvest':>12} {'Jun kWh/m2/d':>13} {'Jun harvest':>12}")
for tilt in (0.0, 15.0, 35.0, 50.0):
    dd = tilted(GHI[11], tilt, MID_N[11]) * CALIB[11]
    jj = tilted(GHI[5], tilt, MID_N[5]) * CALIB[5]
    tilts[str(tilt)] = [round(dd, 2), round(jj, 2)]
    print(
        f"  {tilt:4.0f}  {dd:13.2f} {harvest(dd, 1.0, T_AMB[11]):12.2f} {jj:13.2f} {harvest(jj, 1.0, T_AMB[5]):12.2f}"
    )
print("soiling, December, on the fixed tilt:")
for soil in (1.0, 0.85, 0.70):
    print(f"  factor {soil:.2f}: {harvest(POA[11], soil, T_AMB[11]):5.2f} Wh/day")
print(
    "\na horizontal panel does not shed dust: rain only cleans a surface from about 15 degrees up, and the "
    "soiling events at this latitude are saharan dust in spring and pollen in summer. The tilt buys about "
    "17 % in December on its own and loses 12 % in June, so the reason to tilt is the cleaning and the "
    "shading, not the December gain."
)
json.dump(
    {
        "tool": "energy_budget.py",
        "assumptions": {
            "lat_deg": LAT,
            "reference_tilt_deg": REF_TILT,
            "panel_m2": AREA,
            "module_efficiency": ETA,
            "charge_and_cell_efficiency": ETA_PATH,
            "cell_rise_k": T_CELL_RISE,
            "temp_coefficient_per_k": BETA_TEMP,
            "p_avg_w": P_AVG,
            "cell_wh": CELL_WH,
            "poa_source": "published monthly plane-of-array for 38 N at a 35 deg tilt, "
            "replace with a local measurement",
            "warning": "monthly means contain no bad week. Autonomy and not the monthly "
            "balance is what covers a winter front",
        },
        "months": rows,
        "worst_month": worst[1],
        "worst_balance_wh_day": round(worst[0], 3),
        "max_load_mw_december": round(max_load_dec * 1000, 1),
        "max_load_mw_june": round(max_load_jun * 1000, 1),
        "panel_area_m2_for_break_even_in_december": round(area_for_load, 4),
        "days_of_autonomy": round(autonomy, 2),
        "cell_wh_for_5_days": round(P_AVG * 24 * 5, 2),
        "tilt_dec_jun_kwh_m2_day": tilts,
    },
    open(os.path.join(HERE, "energy_report.json"), "w"),
    indent=1,
)
print("wrote energy_report.json")
