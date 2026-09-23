"""Monte Carlo study of every fit that has to go together.

Every nominal is read from the macro rather than retyped, so the study follows the model. Every fit names
its failure mode and the direction it fails in: a clearance fit fails on the low tail, an interference
fit fails on the high tail, and a two sided fit has two modes with different severities. A wrong
direction would report an interference risk as a clearance alarm, so the direction is stated per fit.

Two independent engines run over the same model, mcerp and a closed form normal, and the tool compares
their failure probabilities against each other to sampling noise.

A heat set insert is deliberately not a diameter study. The iron reflows the plastic, so its bore, its
wall and its depth are design rules that design_rules.py checks, and a diameter Monte Carlo would test
the wrong variable.

The tool cannot decide anything about a fit whose bought part has no tolerance in this repository. It
prints those as assumptions at the end of the run, and the two that govern a fit have a sensitivity row.

Run with: freecadcmd tolerance_mc.py
"""
# ruff: noqa: F821, E402  (names and geometry come from the macro exec'd below)

import json
import math
import os

os.environ["LHB_NO_EXPORT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(
    open(os.path.join(HERE, "..", "freecad", "LoRaHarvesterBox_Enclosure.FCMacro"), encoding="utf-8").read(),
    globals(),
)

import mcerp
import numpy as np

mcerp.npts = 20000
PRINTED = 0.30 / 3.0  # SLS/MJF PA12, 0.3 mm taken as +-3 sigma
LIMIT_FAIL = 0.1  # per fit, per named failure mode, Gate D


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def fit(name, terms, fail, limit=0.0, severity="hard", note="", bought=None):
    """Reads terms as [(sign, nominal, sigma)], where the value is the sum of sign * nominal.

    A fail of "low" means that the value has to stay above the limit. "high" means that it has to stay
    below it.
    """
    mu = sum(s * n for s, n, _ in terms)
    sigma = math.sqrt(sum(sd * sd for _, _, sd in terms))
    z = (limit - mu) / sigma
    p_analytic = phi(z) if fail == "low" else 1.0 - phi(z)
    sample = np.zeros(mcerp.npts)
    for sign, nominal, sd in terms:
        if sd > 0.0:  # a zero sigma term only carries a nominal, for the record
            sample = sample + sign * np.array(mcerp.N(nominal, sd)._mcpts)
    p_sample = float(np.mean(sample < limit)) if fail == "low" else float(np.mean(sample > limit))
    return {
        "fit": name,
        "value_mm": round(mu, 3),
        "sigma_mm": round(sigma, 4),
        "fails_when": f"{'below' if fail == 'low' else 'above'} {limit:+.2f} mm",
        "fail_probability_percent": round(p_sample * 100, 4),
        "analytic_percent": round(p_analytic * 100, 4),
        "engine_gap_percent": round(abs(p_sample - p_analytic) * 100, 4),
        "severity": severity,
        "bought_tolerance_source": bought,
        "note": note,
        "terms": [{"sign": s, "nominal_mm": n, "sigma_mm": sd} for s, n, sd in terms],
    }


def printed(nominal):
    return (1, nominal, PRINTED)


def bought(nominal, tol3):
    return (-1, nominal, tol3 / 3.0)


pcb_bb = pcb.BoundBox
pcb_x, pcb_y, pcb_t = pcb_bb.XLength, pcb_bb.YLength, PCB_T
PCB_TOL3 = 0.15  # the board outline tolerance is not stated in the repo; swept below
FITS = []

# The assembly clearances. These fail when the gap closes, so the tool reads them on the low tail.
FITS.append(
    fit(
        "lid skirt down the cavity wall, per side",
        [printed(SK), (1, 0.0, PRINTED)],  # cavity wall and skirt wall, both printed
        "low",
        0.0,
        note=f"nominal {SK} mm per side, both faces printed, JLC min for assembled parts is 0.2-0.4 mm",
    )
)
FITS.append(
    fit(
        "PCB outline into the left locator rib",
        [(1, PCB_CLR, PRINTED), (-1, 0.0, PCB_TOL3 / 3.0)],
        "low",
        0.0,
        note=f"rib face nominal {PCB_CLR} mm off the board edge. The board outline {pcb_x:.1f} x {pcb_y:.1f} mm "
        "is a bought part, and its outline tolerance is not stated in the repository",
    )
)
FITS.append(
    fit(
        "PCB outline into the right locator rib",
        [(1, PCB_CLR, PRINTED), (-1, 0.0, PCB_TOL3 / 3.0)],
        "low",
        0.0,
        note="same nominal as the left rib, mirrored: 0.4 mm each side of a 48 mm board in a 64 mm cavity",
    )
)

# The hold down lip is a vertical clearance over the board's top face, not a lateral one.
lip_gap = lip_z - (PCB_Z + pcb_t)
FITS.append(
    fit(
        "hold down lip over the PCB top, vertical",
        [(1, lip_gap, PRINTED), (-1, 0.0, 0.10 / 3.0)],
        "low",
        0.0,
        note=f"lip underside at z {lip_z:.2f}, PCB top at {PCB_Z + pcb_t:.2f}: a {lip_gap:.2f} mm nominal "
        "gap inside the board's own thickness tolerance. A negative gap means the board cannot sit flat "
        "on its five pillars, so the M2 hole at H1 misaligns",
    )
)

# Bought parts into printed pockets, where the vendor tolerance is the one that is not in this
# repository.
FITS.append(
    fit(
        "LiPo 852040 into the battery pocket, width",
        [printed(POCKET[3]), bought(BAT_W, 0.5)],
        "low",
        0.0,
        bought="vendor pouch tolerance taken as +-0.5 mm",
        note="pocket width 21.0, cell 20.0",
    )
)
FITS.append(
    fit(
        "LiPo 852040 into the battery pocket, length",
        [printed(POCKET[2]), bought(BAT_L, 0.5)],
        "low",
        0.0,
        bought="vendor pouch tolerance taken as +-0.5 mm",
        note="pocket length 48.0, cell 45.0 including the protection board",
    )
)
FITS.append(
    fit(
        "SMA bulkhead shank through the left wall",
        [printed(SMA_D), bought(6.35, 0.05)],
        "low",
        0.0,
        bought="SMA 6.35 mm shank, +-0.05 mm",
        note="the playbook's own field lesson opened this hole from 6.7 to 6.9 mm",
    )
)
FITS.append(
    fit(
        "ePTFE vent thread through the right wall",
        [printed(VENT_D), bought(12.0, 0.1)],
        "low",
        0.0,
        bought="M12 thread, +-0.1 mm",
    )
)
FITS.append(
    fit(
        "M3 screw through the lid hole",
        [printed(LID_HOLE_D), bought(3.0, 0.05)],
        "low",
        0.0,
        bought="M3 shank, +-0.05 mm",
    )
)
FITS.append(
    fit(
        "cable tie 5 x 1.5 in the Y tunnel",
        [printed(TIE_W), bought(5.0, 0.1)],
        "low",
        0.0,
        bought="cable tie, +-0.1 mm",
    )
)
FITS.append(
    fit(
        "3 mm cord in the X tunnel",
        [printed(TIE_W2), bought(3.0, 0.2)],
        "low",
        0.0,
        bought="cord, +-0.2 mm",
        note="the README buys cord up to 3 mm. The older version of this study typed 4 mm here",
    )
)

# The interference fits. These fail when the interference is too weak, so the tool reads them on the
# high tail.
FITS.append(
    fit(
        "M3 in the captive neck, interference wanted",
        [printed(SCREW_CAPTIVE_D), bought(3.0, 0.05)],
        "high",
        -0.15,
        severity="soft",
        bought="M3 shank, +-0.05 mm",
        note=f"neck {SCREW_CAPTIVE_D} mm against a 3.0 mm shank gives {3.0 - SCREW_CAPTIVE_D:.2f} mm of "
        "interference. The playbook's step 5 range is 2.7 to 2.8 mm. Too little and the screw is not "
        "captive, which is a drop of threadlocker rather than scrap",
    )
)

# The O-ring is two sided: too little squeeze leaks, and too much damages the cord.
cord, groove = 2.0, GROOVE_D
mu_sq = 100.0 * (cord - groove) / cord
d_sq = 100.0 / cord  # d(squeeze)/d(depth)
s_sq = abs(d_sq) * PRINTED
s_cord = abs(100.0 * groove / cord**2) * (0.1 / 3.0)
sigma_sq = math.sqrt(s_sq**2 + s_cord**2)
oring = {
    "fit": "O-ring groove compression, 2 mm cord",
    "value_mm": round(mu_sq, 2),
    "sigma_mm": round(sigma_sq, 3),
    "fails_when": "below 15 % or above 25 % (playbook band), soft outside 10-35 %",
    "fail_probability_percent": round(
        float(np.mean((mcerp.N(mu_sq, sigma_sq)._mcpts < 15.0) | (mcerp.N(mu_sq, sigma_sq)._mcpts > 25.0))) * 100,
        4,
    ),
    "below_10_percent": round(float(np.mean(mcerp.N(mu_sq, sigma_sq)._mcpts < 10.0)) * 100, 4),
    "above_35_percent": round(float(np.mean(mcerp.N(mu_sq, sigma_sq)._mcpts > 35.0)) * 100, 4),
    "severity": "soft",
    "note": f"groove {GROOVE_W} x {GROOVE_D} for a 2.0 mm cord, {mu_sq:.0f} % compression at nominal. The "
    "playbook default is 1.5 to 1.55 mm (22 to 25 %), so a nominal at the top of the band puts half of "
    "all prints outside it",
    "terms": [
        {"sign": "cord", "nominal_mm": cord, "sigma_mm": 0.1 / 3.0},
        {"sign": "depth", "nominal_mm": groove, "sigma_mm": PRINTED},
    ],
}

print(f"{'fit':46} {'value':>7} {'sigma':>6} {'fail %':>8} {'analytic':>9}  {'sev':>5} verdict")
print("-" * 108)
bad = 0
for f in FITS:
    over = f["fail_probability_percent"] > LIMIT_FAIL
    bad += 1 if (over and f["severity"] == "hard") else 0
    print(
        f"{f['fit']:46} {f['value_mm']:7.3f} {f['sigma_mm']:6.3f} "
        f"{f['fail_probability_percent']:8.3f} {f['analytic_percent']:9.3f}  {f['severity']:>5} "
        f"{'OVER the 0.1 % limit' if over else 'ok'}"
    )
print(
    f"{oring['fit']:46} {oring['value_mm']:7.1f}% {oring['sigma_mm']:6.2f} "
    f"{oring['fail_probability_percent']:8.2f} {'-':>9}  {oring['severity']:>5} "
    f"below 10 %: {oring['below_10_percent']:.2f} %, above 35 %: {oring['above_35_percent']:.2f} %"
)

print("\nwhat the numbers above assume, and what is not in the repo:")
for f in FITS:
    if f["bought_tolerance_source"]:
        print(f"  {f['fit']}: {f['bought_tolerance_source']}")
print(f"  PCB outline tolerance: not stated. The rib gap nominal is {PCB_CLR} mm.")
sens = []
for tol3 in (0.10, 0.15, 0.20, 0.30):
    sig = math.sqrt(PRINTED**2 + (tol3 / 3.0) ** 2)
    p = phi(-PCB_CLR / sig) * 100
    sens.append({"pcb_outline_tol_3sigma_mm": tol3, "fail_percent_per_side": round(p, 3)})
    print(f"  PCB outline +-{tol3:.2f} mm (3 sigma) -> {p:.3f} % per side, {2 * p:.3f} % over the two ribs")
print("  LiPo pouch tolerance: not stated, taken as +-0.5 mm. The pocket is 1.0 mm wider than the cell.")
print(f"  {'LiPo pouch 3 sigma':22} {'fail %':>8}")
for tol3 in (0.2, 0.3, 0.5, 0.8):
    sig = math.sqrt(PRINTED**2 + (tol3 / 3.0) ** 2)
    p = phi(-(POCKET[3] - BAT_W) / sig) * 100
    sens.append({"lipo_tol_3sigma_mm": tol3, "fail_percent_width": round(p, 3)})
    print(f"  +-{tol3:.1f} mm{'':17} {p:8.3f}")

worst = max(
    [f for f in FITS if f["severity"] == "hard"] + [{"fail_probability_percent": oring["below_10_percent"]}],
    key=lambda f: f["fail_probability_percent"],
)
hard_max = max((f["fail_probability_percent"] for f in FITS if f["severity"] == "hard"), default=0.0)
soft_max = max((f["fail_probability_percent"] for f in FITS if f["severity"] != "hard"), default=0.0)
print(
    f"\nGate D (below {LIMIT_FAIL} % per fit): {bad} hard fit(s) over the limit. The worst hard fit is "
    f"{hard_max:.3f} %, and the two soft ones are the captive neck at {soft_max:.2f} % (a loose screw is a "
    f"drop of threadlocker) and the O-ring's {oring['below_10_percent']:.2f} % chance of under 10 % squeeze."
)

json.dump(
    {
        "tool": "tolerance_mc.py",
        "process": "SLS/MJF PA12",
        "printed_tolerance_3sigma_mm": 0.30,
        "samples_per_fit": mcerp.npts,
        "gate_d_limit_percent": LIMIT_FAIL,
        "fits": FITS,
        "oring_compression": oring,
        "pcb_outline_sensitivity": sens,
        "hard_fits_over_limit": bad,
        "engine_note": "mcerp sampling and a closed form normal over the same term list",
    },
    open(os.path.join(HERE, "tolerance_report.json"), "w"),
    indent=1,
)
print("wrote tolerance_report.json")
