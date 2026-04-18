# Phase 7 — Task 20 VM Restart Status

## Status: DEFERRED

BFS/L5 campaign restart on `root@155.212.128.27` is blocked by two things
that must be resolved before the VM runs v1.0.0 code:

### 1. VM unreachable from cutover worktree

```text
$ ssh -o ConnectTimeout=5 root@155.212.128.27 'systemctl is-active dj-loop'
ssh: connect to host 155.212.128.27 port 22: Operation timed out
```

No network path from the current environment. Restart must be issued from
a machine with SSH access to the Selectel VM.

### 2. VM scripts stubbed with NotImplementedError

Task 17 stubbed `scripts/vm_import_and_analyze.py` and
`scripts/ym_bfs_expand.py` because they target legacy APIs (`app.ym.*`,
`app.services.*`) that were deleted in Chunk C. They must be rewritten
against the v1 surface before they can run.

Deploying them to the VM as-is would cause systemd to flap forever on
`NotImplementedError` exits.

## What to do post-merge

1. **Rewrite VM scripts** against v1 APIs:
   - `app.providers.yandex.client.YandexClient` (was
     `app.ym.client.YandexMusicClient`)
   - `app.providers.yandex.rate_limiter.TokenBucketRateLimiter` (was
     `app.ym.rate_limiter.RateLimiter`)
   - TieredPipeline and service-level helpers need v1 equivalents
     identified — they may live in `app.handlers.*` or need porting.
   - Audit the 1986 lines of script code against the new surface.

2. **Smoke-test locally** with `--test-one` or `--once` before deploying
   to VM.

3. **Rsync + restart** using the systemd-run pattern documented in
   `docs/vm-deployment.md`.

## Scope note

Task 20 rule in the Chunk D prompt explicitly allows deferring this when
infra is unavailable — "DO NOT fail Phase 7". The atomic swap + configs
+ smoke are landed; BFS/L5 resumption is a post-v1.0.0 follow-up.
