# Siax distributed tile runner (experimental)

This is a first executable distributed-inference slice. It is deliberately a filesystem-backed queue, not a claim that GitHub-hosted runners can see a developer's local disk.

## Current contract

- The planner normalizes the source with EXIF transpose + RGB and records both the original file SHA-256 and normalized base_rgb.png SHA-256.
- Every task owns one non-overlapping core rectangle and reads a halo-padded input crop. The worker runs the pinned Siax 4x checkpoint on that crop and writes only the upscaled core to the result.
- Each worker process loads the checkpoint once, then claims multiple tiles.
- Workers claim tasks by atomically moving pending/<task>.json to in_progress/<worker>/<task>.json. The queue root and all queue folders must be on one filesystem with atomic rename semantics.
- The stitcher verifies each task receipt, input hash, checkpoint hash, output hash, output dimensions, overlap and complete source coverage before writing the final RGB uint8 PNG.
- The output and sidecar remain candidate_only; seam deltas are diagnostic, not a quality score or acceptance gate.

## Commands

Install the optional Siax runtime on each machine:

~~~bash
python -m pip install -e '.[upscale]'
~~~

Review checkpoint terms and verify the pinned checkpoint is available on each worker. The job does not copy the checkpoint into the queue.

Plan the job once:

~~~bash
ige siax-distribute-plan BASE.png --job-dir runs/siax-job --tile-size 128 --tile-pad 8
~~~

Start one worker per machine/process. Give every concurrent process a unique worker ID:

~~~bash
ige siax-distribute-worker runs/siax-job --checkpoint models/4x_NMKD-Siax_200k.pth --worker-id local-cpu --device cpu --confirm-model-license-review
~~~

~~~bash
ige siax-distribute-worker runs/siax-job --checkpoint models/4x_NMKD-Siax_200k.pth --worker-id local-gpu --device cuda --confirm-model-license-review
~~~

When all pending tasks have been claimed and completed, stitch:

~~~bash
ige siax-distribute-stitch runs/siax-job --out runs/siax-4x.png
~~~

The worker exits when it sees no pending task. It does not wait for another worker's in-progress task. Run the stitcher only after all workers have exited successfully; otherwise the stitcher refuses an incomplete job. A crashed worker leaves an in-progress claim that must be manually returned to pending/ after confirming the original process is dead. Automatic lease expiry/reclamation is not in this first slice.

## GitHub-hosted and local concurrency: an important boundary

A GitHub-hosted runner cannot mount runs/siax-job on a private desktop merely because both processes run under GitHub Actions. Real simultaneous work across a hosted runner and local machine needs a shared, authenticated object store/queue or a deliberate bundle hand-off.

Supported immediately:
- multiple local worker processes sharing a local directory;
- multiple remote workers sharing a secured NFS/SMB or equivalent filesystem whose rename semantics have been verified;
- a secured self-hosted GitHub Actions runner on a machine that can access the same job directory.

Not implemented yet:
- S3/Azure/GCS object-store adapters;
- GitHub Actions artifact shard upload/download orchestration;
- a remote lease/heartbeat service;
- automatic stale-claim recovery;
- measured throughput-based weighted scheduling.

For a hosted GitHub runner, use an explicit artifact hand-off: export disjoint task shards, execute them on hosted workers, download the result artifacts back into the job folder, and then stitch. That is batch fan-out/fan-in, not a live shared queue. Never expose a private desktop folder or long-lived personal token to an untrusted workflow to fake shared access.

## Fairness and numerical consistency

A worker is not assigned a fixed percentage. It claims the next available tile after completing its previous tile, so faster workers naturally process more. This is work-conserving dynamic allocation, but it does not yet use a pilot benchmark or predicted runtime weights.

All workers must use the same pinned checkpoint and preprocessing. Different CPU/GPU kernels can produce small numeric differences. This implementation records device and worker identity but does not claim CPU/GPU pixel identity. Compare same-machine single-worker and mixed-worker outputs before treating a mixed result as equivalent. Do not change precision or model settings by worker in the same job.

## Tile boundaries

The worker receives the tile_pad halo and emits only the core region. This avoids writing overlapping output pixels and prevents the stitcher from blending two independently inferred versions of the same core. It does not guarantee seam-free model output: the seam diagnostics only report mean adjacent-pixel deltas along tile boundaries. Human visual review and a same-BASE single-worker reference comparison remain required.

## Scope not claimed

- This does not execute real Siax inference in CI; tests use synthetic tile images to exercise queue ownership, receipts, hashing, coverage and stitching.
- No project image has been run through this distributed path yet.
- No speedup claim is made. Network transfer, image encoding, checkpoint load, CPU/GPU throughput and queue contention can erase parallel gains.
- Final identity, geometry, topology, material and perceptual acceptance remain separate gates.
