# L5 Library Sweep on a Selectel Cloud VM — Runbook

> Step-by-step that **actually worked** (2026-06-23) for spinning up a
> CPU VM on Selectel Cloud (OpenStack), deploying the project, and running
> the full-library **L5 (ADVANCED / essentia) analysis sweep**. Every
> gotcha we hit is documented with its fix so we never re-solve them.

All Selectel credentials live in the gitignored root `.env` under the
`SEL_*` prefix (24 vars). Never commit them; never echo the password.

---

## 0. TL;DR — re-provision from scratch

```bash
# auth (openrc from .env values)
cat > /tmp/.sel_openrc <<'X'
export OS_AUTH_URL=https://cloud.api.selcloud.ru/identity/v3
export OS_USERNAME='Lexia'
export OS_PASSWORD='<SEL_OS_PASSWORD from .env>'
export OS_USER_DOMAIN_NAME='229725'
export OS_PROJECT_DOMAIN_NAME='229725'
export OS_PROJECT_ID='02bfcb0a95d344539e07669c2d2d1f7a'   # "DJ Music"
export OS_IDENTITY_API_VERSION=3
export OS_INTERFACE=public
export OS_REGION_NAME=ru-3
X
chmod 600 /tmp/.sel_openrc && source /tmp/.sel_openrc

# keypair from our private key
openstack keypair create --public-key ~/.ssh/dj_l5_selectel.pub dj-l5-key

# network: private net + subnet + router to external + SG rules
openstack network create dj-l5-net
openstack subnet create --network dj-l5-net --subnet-range 192.168.100.0/24 \
  --dns-nameserver 8.8.8.8 --dns-nameserver 1.1.1.1 dj-l5-subnet
openstack router create dj-l5-router
openstack router set --external-gateway external-network dj-l5-router
openstack router add subnet dj-l5-router dj-l5-subnet
openstack security group rule create --proto tcp --dst-port 22 --remote-ip 0.0.0.0/0 default
openstack security group rule create --proto icmp default

# bootable volume — type MUST match the AZ (ru-3b here, see Pitfall 5/6)
openstack volume create --image b17b997b-46db-48ec-8f6f-6952251a72b6 --size 50 \
  --type universal.ru-3b --availability-zone ru-3b --bootable dj-l5-boot-3b

# server — AMD-zen4 flavor is ru-3b ONLY (see Pitfall 5)
openstack server create --flavor 1059 --volume dj-l5-boot-3b \
  --availability-zone ru-3b --network dj-l5-net --key-name dj-l5-key dj-l5-vm

# floating IP
openstack floating ip create external-network          # → 139.100.203.69
openstack server add floating ip dj-l5-vm 139.100.203.69

# login is ROOT, not ubuntu
ssh -i ~/.ssh/dj_l5_selectel root@139.100.203.69
```

---

## 1. The instance we run

| Thing | Value |
|---|---|
| Region / AZ | `ru-3` / **`ru-3b`** |
| Project | `DJ Music` (`02bfcb0a95d344539e07669c2d2d1f7a`) |
| Flavor | **`1059` = SL2.8-16384-AMD** — 8 vCPU AMD zen4 **dedicated/pinned**, 16 GB |
| Image | `b17b997b-46db-48ec-8f6f-6952251a72b6` (Ubuntu 22.04 LTS) |
| Boot volume | `dj-l5-boot-3b`, 50 GB, type `universal.ru-3b` |
| Network | `dj-l5-net` (private) → router → `external-network` |
| Floating IP | `139.100.203.69` |
| Keypair | `dj-l5-key` (our `~/.ssh/dj_l5_selectel`) |
| **Login** | **`root@139.100.203.69`** |

---

## 2. Pitfalls we hit and how we fixed them

### P1 — Old resell API is dead (404)
`https://api.selectel.ru/vpc/resell/v2/...` → **404**. Selectel migrated.
**Fix:** use OpenStack Identity at `https://cloud.api.selcloud.ru/identity/v3`.

### P2 — A bare "API token" is not enough; you need a **service user**
A standalone token 401'd on every endpoint. Cloud-server creation is pure
OpenStack and needs a **service user** (panel → Управление доступом →
Сервисные пользователи). Auth = username + password + **domain = account
number** (`229725`), NOT the user UID.
```text
OS_USERNAME=Lexia   OS_USER_DOMAIN_NAME=229725   OS_PASSWORD=...
```

### P3 — `openstack project list` → 403
The service user can't list domain projects.
**Fix:** the projects it *does* have roles in come from the token itself:
```bash
TOKEN=$(openstack token issue -f value -c id)
curl -s -H "X-Auth-Token: $TOKEN" \
  https://cloud.api.selcloud.ru/identity/v3/auth/projects | jq '.projects[]'
# → 02bfcb0a... "DJ Music"
```

### P4 — You must scope to a region
Unscoped catalog is empty. Set `OS_REGION_NAME=ru-3` (regions: ru-1…ru-5,
kz-1, gis-1/2, ke-1).

### P5 — Flavors are pinned to a **segment/AZ** (the big one)
`server create` fails with `conductor_schedule_and_build_instances: Error`
(NoValidHost) or `availability zone is not suitable for the requested
instance type`. Flavors carry a hidden constraint — inspect it:
```bash
openstack flavor show 1059 -f json | jq '.properties'
# "aggregate_instance_extra_specs:fl_size": "standard_3b_amd_zen4_pinned_ht"
openstack flavor show 1025 -f json | jq '.properties'
# "...:fl_size": "<or> cpu_3a_v3 <or> cpu_3b_amd"
```
- **SL2 AMD-zen4 (1059)** → **ru-3b only**.
- **SL1 (1025)** → ru-3a (Intel v3) *or* ru-3b — but ru-3a had **no free
  hosts** for us (NoValidHost).
**Fix:** match flavor's `fl_size` segment to the AZ. We use **`1059` in
`ru-3b`** (and it gives dedicated pinned cores — best for CPU-bound L5).

### P6 — Volume types are AZ-bound
`universal.ru-3a` vs `universal.ru-3b`. The volume's type/AZ **must** match
the server's AZ. Mismatch → the original `ru-3b is invalid` error.

### P7 — Don't use `--boot-from-volume <size>`
The auto-created volume lands in the wrong AZ/type → schedule failure.
**Fix:** create the bootable volume **explicitly** (P6 type), then
`server create --volume <id>`.

### P8 — `--name` is wrong for `server create`
Name is a **positional** arg: `openstack server create ... dj-l5-vm`.

### P9 — SSH login is `root`, not `ubuntu`
Selectel's Ubuntu image places the key for **root**.

### P10 — uv picks Python 3.14; essentia has no cp314 wheel
`uv sync` defaulted to CPython 3.14 → `essentia` won't install
(`cp312`/`cp313` wheels only).
**Fix on the VM:** `uv python pin 3.12 && uv sync --all-extras`.

---

## 3. Deploy on the VM

```bash
ssh -i ~/.ssh/dj_l5_selectel root@139.100.203.69
# system deps for essentia/librosa
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y git ffmpeg build-essential python3-dev python3-venv \
  libsndfile1 libfftw3-3 libyaml-0-2 libtag1v5 libsamplerate0 curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Push code + `.env` from the laptop (exclude heavy/dev dirs):
```bash
rsync -az -e "ssh -i ~/.ssh/dj_l5_selectel" \
  --exclude '.git/' --exclude '.venv/' --exclude 'generated-sets/' \
  --exclude 'cache/' --exclude '__pycache__/' --exclude 'tests/' --exclude 'docs/' \
  /Users/laptop/dev/dj-music-plugin/ root@139.100.203.69:/root/dj-music-plugin/
```
Build the env (note the **3.12 pin**):
```bash
cd /root/dj-music-plugin
export PATH=$HOME/.local/bin:$PATH
uv python pin 3.12
uv sync --all-extras
uv run python -c "import librosa, essentia, soundfile; print(librosa.__version__, essentia.__version__)"
# → 0.11.0 2.1-beta6-dev
```

---

## 4. Run the L5 sweep

The sweep script is `scripts/vm_l5_sweep.py` (continuous, **resumable** —
only touches `analysis_level < 5`, restart-safe; temp-download → analyze →
delete; parallel; per-track progress logs).

```bash
cd /root/dj-music-plugin && export PATH=$HOME/.local/bin:$PATH
# smoke test FIRST (1 track, confirm essentia features land):
uv run python -u scripts/vm_l5_sweep.py --limit 1

# full run under tmux so it survives SSH drop:
tmux new -s l5 -d "PYTHONUNBUFFERED=1 uv run python -u scripts/vm_l5_sweep.py \
  --workers 8 --batch 200 2>&1 | tee -a /var/log/dj_l5.log"
# watch:  ssh ... 'tail -f /var/log/dj_l5.log'
```
DB: the VM is a normal Selectel host (no egress proxy), so **asyncpg :6543
to Supabase works directly** — unlike the cloud sandbox. The script reads
DB creds from `/root/dj-music-plugin/.env`.

Estimated wall-clock: ~24k tracks at ~15–30 s each across 8 cores ≈
**10–20 hours**. Resume after any interruption by just re-running the same
command.

---

## 5. Cleanup (stop billing) when the sweep is done

```bash
source /tmp/.sel_openrc; export OS_REGION_NAME=ru-3
openstack server delete dj-l5-vm
openstack volume delete dj-l5-boot-3b
openstack floating ip delete 139.100.203.69
openstack router remove subnet dj-l5-router dj-l5-subnet
openstack router unset --external-gateway dj-l5-router
openstack router delete dj-l5-router
openstack subnet delete dj-l5-subnet
openstack network delete dj-l5-net
# keep dj-l5-key keypair — cheap, reusable
```

---

## 6. After the sweep — the actual point

L5 populates the essentia discriminators (`danceability`, `dissonance`,
`dynamic_complexity`, `spectral_complexity`, `pitch_salience`, `tonnetz`,
…) that the **mood classifier** was designed around but which are NULL on
the L2 library. Then: recalibrate `app/audio/classification/profiles.py`
`ideal`/`tolerance` to the **real** essentia distributions and add
confidence-gating (low margin → `mood = unknown` instead of guessing).
See the classifier diagnosis in this session / `scripts/diag_mood_classifier.py`.

---

## 7. L6 Deep Track Analysis on the VM

L6 requires **GPU** for Demucs stem separation (CPU is too slow). On this
VM (8 vCPU, no GPU) we run L6 **without stems** — still produces pgvector
embeddings, beatgrid, structural sections, and all L6-only analyzers
(chords, HPCP, inharmonicity, meter, audio QA).

```bash
cd /root/dj-music-plugin && export PATH=$HOME/.local/bin:$PATH

# Pull L6 code (after merge to main)
git pull

# Smoke test — L6 on one track (no Demucs, ~2 min)
uv run python -c "
import asyncio, json
from app.db.session import get_session_factory
from app.providers.supabase.storage_client import SupabaseStorageClient
from app.repositories.unit_of_work import UnitOfWork
from app.domain.deep_analysis.orchestrator import L6AnalysisOrchestrator

async def run():
    factory = get_session_factory()
    async with factory() as session:
        uow = UnitOfWork(session)
        storage = SupabaseStorageClient(url='', key='')
        orch = L6AnalysisOrchestrator(storage_client=storage)
        result = await orch.run(track_id=146, uow=uow)
        await session.commit()
        print(json.dumps({
            'stem_features': result.stem_features_count,
            'beatgrid': result.beatgrid_registered,
            'sections': result.sections_count,
            'embeddings': result.embeddings_count,
        }, indent=2))
asyncio.run(run())
"

# Full L6 sweep — only tracks with local files, skip already-done
# (L6 resumable: tracks with stem_features skip Demucs, partial runs skip themselves)
```

### When you get a GPU instance

1. Provision a VM with **NVIDIA Tesla T4** or similar (Selectel Cloud →
   GPU compute). 200 GB volume for stems.
2. Install CUDA + PyTorch CUDA.
3. Run the full L6 sweep — Demucs will auto-detect CUDA and produce 4 stems
   per track (~30s/track with GPU):

```bash
uv run python -u scripts/vm_l6_sweep.py --workers 4 --batch 200 2>&1 | tee -a /var/log/dj_l6.log
```

### What L6 gives you

| Component | With GPU (stemmed) | Without GPU |
|-----------|-------------------|-------------|
| Per-stem features (×5) | ✅ full | ⛔ skip |
| Drum band analysis | ✅ 4 bands | ⛔ skip |
| pgvector embeddings | ✅ 5 types × 256d | ✅ same |
| Beatgrid per track | ✅ | ✅ same |
| Sections + per-stem energy | ✅ | ✅ sections only |
| L6 analyzers (chords, meter, …) | ✅ | ✅ same |
| Supabase Storage | ✅ | ✅ same |
