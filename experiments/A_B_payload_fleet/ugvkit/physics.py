"""Energy and time per km versus load, computed with the frozen simulator's own motion functions (nothing modified).
Reproduces the payload mechanism numbers in protocols/PROTOCOLS.md: cruise time per km is load-independent, energy per km
is a0 + a1*n, and rho = a1/a0 is the share of insertion energy that is not proportional to duration.
usage: python bin/physics.py --repo REPO [--masses 825:80 586.5:80 455.8:80 455.8:100 455.8:160]
"""
import argparse, os, shutil, sys, tempfile
from .common import repo_paths

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--repo", required=True)
    ap.add_argument("--masses", nargs="+", default=["825:80", "586.5:80", "455.8:80", "455.8:100", "455.8:160"])
    a = ap.parse_args(argv)
    app_src, graph, hot = repo_paths(a.repo)
    d = tempfile.mkdtemp(prefix="ugv_physics_")
    shutil.copy2(app_src, os.path.join(d, "app.py")); shutil.copy2(graph, os.path.join(d, "utp_graph.graphml")); shutil.copy2(hot, os.path.join(d, "hotspot_locations.csv"))
    sys.path.insert(0, d); cwd = os.getcwd(); os.chdir(d)
    import app
    os.chdir(cwd)
    def leg(L, mass):
        v = 0.0; rem = float(L); E = 0.0; T = 0.0
        while rem > 1e-9 or v > 1e-9:
            nv, acc, F, dt, dx = app.calculate_stop_motion_step(v, mass, rem, app.DT_S)
            E += app.calculate_driving_energy_Wh(F, dx, dt); T += dt; rem = max(0.0, rem - dx); v = nv
        return E, T
    print("empty_kg passenger_kg | empty Wh/km a0 | per-passenger Wh/km a1 | rho=a1/a0 | cruise s/km (empty, full) | stop-start overhead Wh (empty, full) | full-load mass kg")
    for spec in a.masses:
        m0, mp = (float(x) for x in spec.split(":"))
        cap = app.UGV_PASSENGER_CAPACITY
        e = {}; t = {}; o = {}
        for n in (0, cap):
            E1, T1 = leg(1000, m0 + n * mp); E2, T2 = leg(2000, m0 + n * mp)
            e[n] = E2 - E1; t[n] = T2 - T1; o[n] = E1 - (E2 - E1)
        a1 = (e[cap] - e[0]) / cap
        print(f"{m0:7.1f} {mp:6.1f} | {e[0]:6.2f} | {a1:6.3f} | {100*a1/e[0]:5.1f}% | {t[0]:.1f}, {t[cap]:.1f} | {o[0]:.2f}, {o[cap]:.2f} | {m0 + cap*mp:.0f}")
    shutil.rmtree(d, ignore_errors=True)
    return 0
