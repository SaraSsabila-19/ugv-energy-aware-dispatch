"""Shared helpers: hashing, protocol expansion, run specs. Standard library only."""
import hashlib, json, os, itertools, platform, sys, time
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent

# Fixed simulator CLI settings shared by every run (identical to the published S4/S5 and 2x2 campaigns).
BASE_CLI = {
    "max_sim_s": 14400, "flush_every": 200, "depot_layout": "three",
    "dispatch_window_s": 30, "dispatch_urgent_slack_s": 60,
    "cost_mode": "normalized", "energy_reference_wh": 100, "time_reference_s": 600,
}
BASE_ENV = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
            "V2_DEPOT_LAYOUT": "three", "V2_THREE_DEPOT_IDS": "P02,P08,P16"}
# Only these module constants may be overridden at run time. Each override is recorded per run.
ALLOWED_OVERRIDES = {"UGV_EMPTY_MASS_KG", "UGV_PASSENGER_MASS_KG", "UGV_MASS_KG", "ARRIVAL_WINDOW_S"}
BUILTIN_SCENARIOS = {"S1": (12, 30), "S2": (18, 50), "S3": (24, 100), "S4": (12, 100)}
FROZEN_SEEDS = set(range(1001, 20002, 1000))

def sha256_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()

def sha256_json(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def write_json(p, obj):
    p = Path(p); tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, p)

def seeds_from(spec):
    """'start:stop:step' (inclusive) or a list."""
    if isinstance(spec, list):
        return [int(s) for s in spec]
    a, b, c = (int(x) for x in str(spec).split(":"))
    return list(range(a, b + 1, c))

def repo_paths(repo):
    repo = Path(repo).expanduser().resolve()
    app = repo / "src" / "frozen" / "app.py"
    graph = repo / "inputs" / "utp_graph.graphml"
    if not graph.exists():
        alt = repo / "inputs" / "utp_graph.graphml.xml"  # some downloads rename the file
        if alt.exists():
            graph = alt
    hot = repo / "inputs" / "hotspot_locations.csv"
    for p in (app, graph, hot):
        if not p.exists():
            raise SystemExit(f"Required file not found: {p}")
    return app, graph, hot

def expand_protocol(protocol):
    """Expand a protocol's design into a list of run specs (dicts)."""
    d = protocol["design"]
    seeds = seeds_from(d["seeds"])
    bad = sorted(set(seeds) & (FROZEN_SEEDS | set(protocol.get("excluded_seeds", []))))
    if bad:
        raise SystemExit(f"Protocol {protocol['protocol_id']} uses excluded seeds: {bad[:10]}")
    specs = []
    for fc in d["fleet_configs"]:
        for mc in d["mass_configs"]:
            for alg, soc, alpha in itertools.product(d["algorithms"], d["initial_soc"], d["alpha_energy"]):
                for seed in seeds:
                    vehicles, requests = fc["vehicles"], fc["requests"]
                    overrides = dict(mc.get("overrides", {}))
                    if "UGV_EMPTY_MASS_KG" in overrides:
                        overrides["UGV_MASS_KG"] = overrides["UGV_EMPTY_MASS_KG"]  # alias copied at import
                    for k in overrides:
                        if k not in ALLOWED_OVERRIDES:
                            raise SystemExit(f"Override {k} is not allowed")
                    label = (f"{protocol['protocol_id']}__{fc['id']}__{mc['id']}__{alg}__soc{int(round(soc*100))}"
                             f"__a{alpha:g}__seed{seed}")
                    specs.append({
                        "label": label, "protocol_id": protocol["protocol_id"], "seed": seed,
                        "fleet_config": fc["id"], "vehicles": vehicles, "requests": requests,
                        "mass_config": mc["id"], "algorithm": alg, "initial_soc": soc,
                        "alpha_energy": alpha, "beta_time": d.get("beta_time", 1.0), "soc_cost_weight": d.get("soc_cost_weight", 0.0),
                        "overrides": overrides,
                        # The probe re-solves matrices, so it is only allowed for deterministic, stateless solvers.
                        "probe": {"enabled": bool(d.get("probe", False)) and alg in ("hungarian", "greedy"),
                                  "alpha_alt": (1.0 - alpha) if alpha in (0, 1) else 0.0},
                        "cli": dict(BASE_CLI), "env": dict(BASE_ENV),
                    })
    return specs

def spec_hash(spec):
    return sha256_json({k: v for k, v in spec.items() if k != "label"} | {"label": spec["label"]})

def environment_record():
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
