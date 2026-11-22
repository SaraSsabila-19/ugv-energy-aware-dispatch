"""Run a protocol's simulations with resume, failure detection and no overwriting.

Layout of a campaign folder (OUT):
  .ugvkit_campaign.json      protocol id + protocol SHA-256 (a folder is never reused for another protocol)
  runs/<label>/              one folder per simulation: run_spec.json, app.py copy, inputs, stdout/stderr,
                             overrides_and_provenance.json, probe_stats.json (if probed), results/<run_id>/...
  runs/<label>/RUN_OK.json   written only after the run finished AND passed the per-run checks
  runs/<label>/RUN_FAILED.json  written when a run failed (it is retried on the next launch)
  _incomplete/               earlier attempts that never finished, moved aside (never deleted)
  campaign_log.csv           one line per attempt
"""
import argparse, csv, fcntl, json, os, re, shutil, signal, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from . import FROZEN_APP_SHA256
from .common import (KIT_ROOT, expand_protocol, load_json, repo_paths, sha256_file, spec_hash, write_json, sha256_json)

LOCK = threading.Lock()
STOP = threading.Event()   # set on Ctrl-C: no new runs start, running ones are terminated
ACTIVE = set()             # running simulator processes

def parse_final_status(stdout):
    stdout = stdout.strip()
    try:
        return json.loads(stdout)
    except Exception:
        idx = stdout.rfind("\n{")
        return json.loads(stdout[idx + 1:] if idx >= 0 else stdout[stdout.find("{"):])

def check_run(rd, spec):
    """Per-run checks after the simulator exits. Returns (ok, info)."""
    info = {}
    st = parse_final_status((rd / "stdout.txt").read_text(encoding="utf-8", errors="replace"))
    if st.get("status") != "completed" or st.get("error") is not None:
        return False, {"reason": f"simulator status {st.get('status')} error {st.get('error')}"}
    if int(st["trial_seed"]) != int(spec["seed"]) or st["algorithm"] != spec["algorithm"]:
        return False, {"reason": "seed or algorithm mismatch in simulator output"}
    res = Path(st["results_dir"]).resolve()
    if res.parent != (rd / "results").resolve():
        return False, {"reason": f"results written outside the run folder: {res}"}
    need = ["run_summary.csv", "run_settings.json", "backend_source.py", "canonical_requests.sha256",
            "vehicle_soc_snapshots.csv", "energy_feasibility_summary.csv", "cost_diagnostics.csv",
            "request_results.csv", "request_wait_diagnostics.csv"]
    missing = [n for n in need if not (res / n).exists()]
    if missing:
        return False, {"reason": f"missing outputs {missing}"}
    if sha256_file(res / "backend_source.py") != FROZEN_APP_SHA256:
        return False, {"reason": "archived simulator source is not the frozen FIX-19 app.py"}
    prov = load_json(rd / "overrides_and_provenance.json")
    if prov.get("app_sha256") != FROZEN_APP_SHA256:
        return False, {"reason": "run-folder app.py hash mismatch"}
    if spec["probe"]["enabled"] and not (rd / "probe_stats.json").exists():
        return False, {"reason": "probe enabled but probe_stats.json missing"}
    summ = next(csv.DictReader(open(res / "run_summary.csv")))
    if int(summ["spawned_requests"]) != spec["requests"] or int(summ["fleet_size"]) != spec["vehicles"]:
        return False, {"reason": "fleet size or request count mismatch"}
    info.update(results_dir=str(res.relative_to(rd)), run_summary_sha256=sha256_file(res / "run_summary.csv"),
                canonical_requests_sha256=(res / "canonical_requests.sha256").read_text().split()[0],
                completed_requests=int(summ["completed_requests"]))
    return True, info

def run_one(spec, out, app_src, graph_src, hot_src, py, timeout, retries):
    runs = out / "runs"; rd = runs / spec["label"]; h = spec_hash(spec)
    okf = rd / "RUN_OK.json"
    if okf.exists():
        ok = load_json(okf)
        if ok.get("spec_hash") != h:
            raise SystemExit(f"{spec['label']}: finished run exists with a DIFFERENT spec; refusing to touch it.")
        return spec["label"], "skipped", 0.0
    attempt = 0
    while True:
        attempt += 1
        if STOP.is_set():
            return spec["label"], "not started (interrupted)", 0.0
        if rd.exists():
            dest = out / "_incomplete" / f"{spec['label']}__{time.strftime('%Y%m%dT%H%M%S')}_{os.getpid()}_{attempt}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(rd), str(dest))
        rd.mkdir(parents=True)
        shutil.copy2(app_src, rd / "app.py"); shutil.copy2(graph_src, rd / "utp_graph.graphml"); shutil.copy2(hot_src, rd / "hotspot_locations.csv")
        write_json(rd / "run_spec.json", spec)
        env = dict(os.environ); env.update(spec["env"])
        t0 = time.time(); status = "failed"; detail = ""
        try:
            with open(rd / "stdout.txt", "w") as so, open(rd / "stderr.txt", "w") as se:
                p = subprocess.Popen([py, str(KIT_ROOT / "ugvkit" / "runner.py"), "--run-dir", str(rd)],
                                     cwd=rd, env=env, stdout=so, stderr=se, start_new_session=True)
                with LOCK: ACTIVE.add(p)
                try:
                    p.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    p.kill(); p.wait(); raise
                finally:
                    with LOCK: ACTIVE.discard(p)
            if STOP.is_set() and p.returncode != 0:
                detail = "interrupted by user"
            elif p.returncode != 0:
                detail = f"exit code {p.returncode}"
            else:
                ok, info = check_run(rd, spec)
                if ok:
                    write_json(okf, {"spec_hash": h, "attempt": attempt, "wall_s": round(time.time() - t0, 2), **info})
                    status = "ok"
                else:
                    detail = info["reason"]
        except subprocess.TimeoutExpired:
            detail = f"timeout after {timeout}s"
        except Exception as e:  # keep the campaign going; record the failure
            detail = f"{type(e).__name__}: {e}"
        wall = time.time() - t0
        if status != "ok":
            tail = ""
            try:
                tail = (rd / "stderr.txt").read_text(errors="replace")[-2000:]
            except Exception:
                pass
            write_json(rd / "RUN_FAILED.json", {"spec_hash": h, "attempt": attempt, "reason": detail, "stderr_tail": tail})
        with LOCK:
            new = not (out / "campaign_log.csv").exists()
            with open(out / "campaign_log.csv", "a", newline="") as f:
                w = csv.writer(f)
                if new: w.writerow(["time_utc", "label", "attempt", "status", "wall_s", "detail"])
                w.writerow([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), spec["label"], attempt, status, round(wall, 2), detail])
        if status == "ok" or attempt > retries or STOP.is_set():
            return spec["label"], status if status == "ok" else f"FAILED ({detail})", wall

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", required=True); ap.add_argument("--repo", required=True, help="ugv-benchmark-public folder")
    ap.add_argument("--out", required=True, help="campaign folder (new, or one created by this tool for the same protocol)")
    ap.add_argument("--python", default=sys.executable, help="interpreter with the simulator dependencies")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--timeout", type=int, default=3600); ap.add_argument("--max-retries", type=int, default=1)
    ap.add_argument("--match", default=None, help="only run labels matching this regex (e.g. for a partial batch)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-mixed-probe-schema", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    protocol = load_json(a.protocol); specs = expand_protocol(protocol)
    if a.match:
        specs = [s for s in specs if re.search(a.match, s["label"])]
    out = Path(a.out).expanduser().resolve(); app_src, graph_src, hot_src = repo_paths(a.repo)
    if sha256_file(app_src) != FROZEN_APP_SHA256:
        raise SystemExit(f"{app_src} is not the frozen FIX-19 simulator (SHA-256 mismatch). Refusing to run.")
    marker = out / ".ugvkit_campaign.json"
    pid = {"protocol_id": protocol["protocol_id"], "protocol_sha256": sha256_json(protocol)}
    if out.exists() and any(out.iterdir()):
        if not marker.exists():
            raise SystemExit(f"{out} is not empty and was not created by this kit. Choose a new folder; existing results are never touched.")
        m = load_json(marker)
        if m["protocol_id"] != pid["protocol_id"] or m["protocol_sha256"] != pid["protocol_sha256"]:
            raise SystemExit(f"{out} belongs to protocol {m['protocol_id']} ({m['protocol_sha256'][:12]}); this protocol differs. Use a new folder.")
    # v3.1: never mix probe schemas in one campaign. Runs finished by kit v3.0 carry schema-1 probe records.
    legacy = [s["label"] for s in specs if (out / "runs" / s["label"] / "probe_stats.json").exists()
              and "probe_schema_version" not in load_json(out / "runs" / s["label"] / "probe_stats.json")]
    if legacy and not a.allow_mixed_probe_schema:
        raise SystemExit(f"{len(legacy)} finished runs in {out} were produced by kit v3.0 (probe schema 1). Do not add v3.1 runs "
                         f"to this campaign. If it is complete, repair it with scripts/03_repair_experiment.sh; to deliberately "
                         f"continue anyway, pass --allow-mixed-probe-schema.")
    done = sum(1 for s in specs if (out / "runs" / s["label"] / "RUN_OK.json").exists())
    print(f"{protocol['protocol_id']}: {len(specs)} runs in scope, {done} already complete, {len(specs) - done} to run, jobs={a.jobs}")
    if a.dry_run:
        return 0
    out.mkdir(parents=True, exist_ok=True)
    lockf = open(out / ".ugvkit.lock", "w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(f"Another launcher is already running on {out}. Wait for it to finish or stop it first.")
    if not marker.exists():
        write_json(marker, {**pid, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    import shutil as _sh
    _sh.copy2(a.protocol, out / f"protocol_{protocol['protocol_id']}.json")
    # Ctrl-C and `kill <pid>` (SIGTERM) both stop the campaign cleanly, even when the launcher was started in the
    # background of a script (where the shell would otherwise ignore SIGINT).
    def _stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, _stop)
    failures = []; n = 0; t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(run_one, s, out, app_src, graph_src, hot_src, a.python, a.timeout, a.max_retries) for s in specs]
        try:
            for f in as_completed(futs):
                label, status, wall = f.result(); n += 1
                if status not in ("ok", "skipped"):
                    failures.append((label, status))
                if status != "skipped" or n % 50 == 0:
                    print(f"[{n}/{len(specs)}] {status:8s} {wall:6.1f}s {label}  (elapsed {time.time() - t0:.0f}s)", flush=True)
        except KeyboardInterrupt:
            STOP.set()
            with LOCK:
                procs = list(ACTIVE)
            for p in procs:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            ex.shutdown(wait=True, cancel_futures=True)
            print("Interrupted: running simulations were stopped and marked RUN_FAILED; finished runs are kept. "
                  "Rerun the same command to resume.", flush=True)
            return 130
    print(f"Done: {len(specs) - len(failures)} ok/skipped, {len(failures)} failed.")
    for l, s in failures[:20]:
        print("  FAILED", l, s)
    return 1 if failures else 0
