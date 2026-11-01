#!/usr/bin/env python3
"""S1-C one arm: controlled OMP/torch threads + optional taskset affinity."""
from __future__ import annotations
import argparse, json, os, resource, subprocess, sys, time
from pathlib import Path

def peak_rss_mb() -> float:
    # self process only; workers are children — read from /proc after join via children max
    return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0  # Linux KB

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--job-dir', type=Path, required=True)
    ap.add_argument('--checkpoint', type=Path, required=True)
    ap.add_argument('--arm', choices=('single','dual'), required=True)
    ap.add_argument('--threads-total', type=int, default=2)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()

    n = args.threads_total
    env_base = os.environ.copy()
    # pin BLAS/OMP
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        env_base[k] = str(n if args.arm=='single' else max(1, n//2))

    t0 = time.perf_counter()
    workers = []
    if args.arm == 'single':
        env = env_base.copy()
        env['OMP_NUM_THREADS'] = str(n)
        cmd = [
            'taskset','-c','0,1',
            sys.executable,'-m','ige.cli','siax-distribute-worker', str(args.job_dir),
            '--checkpoint', str(args.checkpoint),
            '--worker-id', 's1c-single',
            '--device','cpu',
            '--confirm-model-license-review',
        ]
        # torch threads inside process via env; also set in wrapper
        p = subprocess.run(cmd, capture_output=True, text=True, env=env,
                           cwd=str(Path(__file__).resolve().parents[1]))
        t1 = time.perf_counter()
        if p.returncode != 0:
            print(p.stdout); print(p.stderr); return p.returncode
        w = json.loads(p.stdout)
        workers = [w]
        wall_inf = t1 - t0
    else:
        half = max(1, n//2)
        procs = []
        for wid, cpus, thr in (('s1c-dual-a','0',half),('s1c-dual-b','1',half)):
            env = env_base.copy()
            env['OMP_NUM_THREADS'] = str(thr)
            env['MKL_NUM_THREADS'] = str(thr)
            cmd = [
                'taskset','-c',cpus,
                sys.executable,'-m','ige.cli','siax-distribute-worker', str(args.job_dir),
                '--checkpoint', str(args.checkpoint),
                '--worker-id', wid,
                '--device','cpu',
                '--confirm-model-license-review',
            ]
            procs.append(subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
                                          cwd=str(Path(__file__).resolve().parents[1])))
        outs = []
        for p in procs:
            o,e = p.communicate()
            if p.returncode != 0:
                print(o); print(e); return p.returncode
            outs.append(json.loads(o))
        t1 = time.perf_counter()
        workers = outs
        wall_inf = t1 - t0

    t2 = time.perf_counter()
    ps = subprocess.run([
        sys.executable,'-m','ige.cli','siax-distribute-stitch', str(args.job_dir),
        '--out', str(args.out),
    ], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[1]), env=env_base)
    t3 = time.perf_counter()
    if ps.returncode != 0:
        print(ps.stdout); print(ps.stderr); return ps.returncode
    text = ps.stdout.split('Status:')[0].strip()
    stitch = json.loads(text)

    rec = {
        'arm': args.arm,
        'threads_total': n,
        'affinity': '0,1' if args.arm=='single' else '0 | 1',
        'threads_per_worker': n if args.arm=='single' else max(1,n//2),
        'wall_inference_s': round(wall_inf, 3),
        'wall_stitch_s': round(t3-t2, 3),
        'wall_total_s': round(t3-t0, 3),
        'workers': [{k:w.get(k) for k in ('worker_id','tasks_completed','runtime_seconds','status')} for w in workers],
        'sum_worker_runtime_s': round(sum(w.get('runtime_seconds') or 0 for w in workers), 3),
        'peak_rss_children_mb': round(peak_rss_mb(), 1),
        'output_sha256': stitch.get('output_sha256'),
        'completed_tiles': stitch.get('execution',{}).get('completed_tiles'),
        'match_r1_master': stitch.get('output_sha256')=='3289e3e02928ac688002adc621124ac73d3730f67a5a0d0a5cabe351a6cfd181',
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(rec, indent=2)+'\n')
    print(json.dumps(rec, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
