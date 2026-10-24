#!/usr/bin/env python3
"""Sequential ABBA benchmark of unmodified vs lazy-KV-copy-elision Flash-iOS.

Starts and stops ONLY subprocesses created by this script. Does not touch 11241,
production executables, checkpoints, or other serving processes. Requires a free
test port. All artifacts are written within the project's Testing tree.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_MODEL = ("/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/"
                 "alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE")

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0

def memory_status():
    out = {}
    for cmd, name in [
        (["sysctl", "-n", "vm.swapusage"], "swapusage"),
        (["sysctl", "-n", "vm.memory_pressure"], "memory_pressure")]:
        try:
            x = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            out[name] = x.stdout.strip() if x.returncode == 0 else x.stderr.strip()
        except Exception as e:
            out[name] = repr(e)
    return out

def payload():
    text = ("The diagnostic system records voltage, temperature, memory "
            "pressure, GPU utilization, and event timestamps. " * 75)
    return {
        "model": "qwen3.5",
        "messages": [{"role": "user",
                      "content": text + "\nSummarize these measurements in one sentence."}],
        "stream": False, "max_tokens": 60,
        "temperature": 0, "reasoning_effort": "off",
    }

def ask(port, body, timeout):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.load(resp)
    result["_client_wall_ms"] = round((time.monotonic() - started) * 1000, 2)
    if result.get("error") or result.get("session_invalidated"):
        raise RuntimeError(f"Server error: {str(result)[:500]}")
    return result

def start_server(binary, model, port, log_path, startup_timeout):
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [str(binary), "--model", str(model), "--tiered", "--serve", str(port),
         "--prefill-nrow"],
        stdout=log, stderr=subprocess.STDOUT, cwd=str(binary.parent),
        start_new_session=True)
    deadline = time.monotonic() + startup_timeout
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"Server exited early with code {proc.returncode}; see {log_path}")
            if port_open(port):
                return proc, log
            time.sleep(0.5)
        raise TimeoutError(f"Server failed to listen within {startup_timeout}s; see {log_path}")
    except BaseException:
        stop_server(proc, log)
        raise

def stop_server(proc, log):
    try:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=10)
    finally:
        log.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--control", required=True, type=Path)
    p.add_argument("--modified", required=True, type=Path)
    p.add_argument("--model", default=DEFAULT_MODEL, type=Path)
    p.add_argument("--port", default=11243, type=int)
    p.add_argument("--out", default="Testing/N128-Lazy-KV-Copy-Elision", type=Path)
    p.add_argument("--request-timeout", default=600, type=int)
    p.add_argument("--startup-timeout", default=180, type=int)
    args = p.parse_args()
    args.control = args.control.expanduser().resolve()
    args.modified = args.modified.expanduser().resolve()
    args.model = args.model.expanduser().resolve()
    args.out = args.out.expanduser().resolve()
    if args.port == 11241:
        p.error("Port 11241 is reserved for the main Flash-iOS service.")
    if not args.control.is_file() or not args.modified.is_file():
        p.error("Both --control and --modified must name existing executable files.")
    if not os.access(args.control, os.X_OK) or not os.access(args.modified, os.X_OK):
        p.error("Both candidates must be executable.")
    if not args.model.is_dir():
        p.error("--model directory does not exist.")
    if port_open(args.port):
        p.error(f"Port {args.port} is already in use. Stop that server gracefully first.")
    root = args.out / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root.mkdir(parents=True, exist_ok=False)
    info = {
        "run_dir": str(root), "date": dt.datetime.now().isoformat(),
        "port": args.port,
        "model": str(args.model),
        "control": {"path": str(args.control), "sha256": sha256_file(args.control)},
        "modified": {"path": str(args.modified), "sha256": sha256_file(args.modified)},
        "start_memory": memory_status(),
        "schedule": ["control", "modified", "modified", "control"],
        "steps": [],
        "notes": ["Each step starts a fresh server, runs one identical stateless request, then terminates only that server.",
                  "Execution without --timing. Idle / thermal / Metal contention are not independently gated.",
                  "A response-text match is not a numerical hidden-state equality check."]
    }
    body = payload()
    (root / "payload.json").write_text(json.dumps(body, indent=2) + "\n")
    (root / "manifest.json").write_text(json.dumps(info, indent=2) + "\n")
    try:
        for index, variant in enumerate(info["schedule"], 1):
            if port_open(args.port):
                raise RuntimeError(f"Port {args.port} became occupied by another process; aborting")
            binpath = args.control if variant == "control" else args.modified
            prefix = f"{index:02d}-{variant}"
            print(f"[{index}/4] {variant}: starting {binpath.name}", flush=True)
            proc, log = start_server(binpath, args.model, args.port,
                                     root / (prefix + "-server.log"),
                                     args.startup_timeout)
            try:
                record = {"order": index, "variant": variant,
                          "memory_before": memory_status(),
                          "server_pid": proc.pid}
                result = ask(args.port, body, args.request_timeout)
                (root / (prefix + "-response.json")).write_text(
                    json.dumps(result, indent=2) + "\n")
                record["timings"] = result.get("flash_timings", {})
                record["content"] = result.get("choices", [{}])[0].get("message", {}).get("content")
                record["finish_reason"] = result.get("choices", [{}])[0].get("finish_reason")
                record["client_wall_ms"] = result["_client_wall_ms"]
                info["steps"].append(record)
                print(f"  prefill={record['timings'].get('prefill_ms')}ms "
                      f"tokens={record['timings'].get('prefill_tokens')}", flush=True)
            finally:
                stop_server(proc, log)
            for _ in range(60):
                if not port_open(args.port):
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("Test port remained occupied after child exited")
            (root / "manifest.json").write_text(json.dumps(info, indent=2) + "\n")
        groups = {
            name: [r["timings"]["prefill_ms"] for r in info["steps"]
                   if r["variant"] == name]
            for name in ("control", "modified")
        }
        answers = [r["content"] for r in info["steps"]]
        counts = [r["timings"].get("prefill_tokens") for r in info["steps"]]
        info["summary"] = {
            "control_prefill_ms": groups["control"],
            "modified_prefill_ms": groups["modified"],
            "control_median_ms": statistics.median(groups["control"]),
            "modified_median_ms": statistics.median(groups["modified"]),
            "modified_time_reduction_pct": round(
                100 * (1 - statistics.median(groups["modified"]) /
                       statistics.median(groups["control"])), 2),
            "all_responses_match": all(a == answers[0] for a in answers),
            "all_prefill_counts_match": all(n == counts[0] for n in counts),
        }
        info["end_memory"] = memory_status()
        (root / "manifest.json").write_text(json.dumps(info, indent=2) + "\n")
        print(json.dumps(info["summary"], indent=2), flush=True)
        print("RESULT DIRECTORY:", root, flush=True)
        return 0 if (info["summary"]["all_responses_match"] and
                     info["summary"]["all_prefill_counts_match"]) else 2
    except BaseException as exc:
        info["error"] = repr(exc)
        (root / "manifest.json").write_text(json.dumps(info, indent=2) + "\n")
        print("FAILED:", repr(exc), "\nPartial results in", root, file=sys.stderr)
        raise

if __name__ == "__main__":
    raise SystemExit(main())
