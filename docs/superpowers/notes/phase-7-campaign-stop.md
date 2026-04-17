# Phase 7 — Campaign Stop Record (Task 4)

**Timestamp:** 2026-04-17 (stop attempt during Phase 7 cutover Chunk B)

## VM stop — `root@155.212.128.27`

**VM unreachable** at stop time:

```text
ssh: connect to host 155.212.128.27 port 22: Operation timed out
```

Unable to gracefully `systemctl stop dj-loop dj-bfs`. The transient
`systemd-run` units on the VM will continue under `Restart=on-failure`
until the VM is reachable again. Next time the VM is reachable, run:

```bash
ssh root@155.212.128.27 '
  systemctl stop dj-loop 2>&1 || true
  systemctl stop dj-bfs 2>&1 || true
  systemctl reset-failed dj-loop dj-bfs 2>/dev/null || true
  systemctl is-active dj-loop
'
```

Pre-stop counters from `/opt/dj-music/vm_loop_latest.log` could not be
captured — VM unreachable. Last known state is in
`docs/superpowers/notes/phase-6-complete.md`.

## Local host (`laptop`)

No local BFS/L5 processes running:

```bash
$ pgrep -f ym_bfs_expand; pgrep -f vm_import_and_analyze
# (empty — no processes)
```

Nothing to stop locally.

## Outcome

- Local: clean (no local campaigns running).
- VM: unreachable at stop time — **deferred**. Must be retried before
  Phase 7 swap lands, because after swap the script paths
  (`scripts/vm_import_and_analyze.py`, `scripts/ym_bfs_expand.py`)
  may be renamed/removed.

## Follow-up

If the VM becomes reachable after the doc-rewrite commits land but
before the swap commit, retry the stop command above and append the
outcome + final counters to this file.
