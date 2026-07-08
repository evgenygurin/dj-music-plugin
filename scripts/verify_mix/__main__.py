"""CLI glue: load manifest -> measure -> run checks -> report.

Usage (from the repo root):

    uv run python -m scripts.verify_mix path/to/manifest.json
    uv run python -m scripts.verify_mix path/to/mix.mp3        # standalone
    uv run python -m scripts.verify_mix manifest.json --json report.json
    uv run python -m scripts.verify_mix manifest.json --pre-only

Exit code is non-zero on any FAIL, so delivery can be gated:

    uv run python -m scripts.verify_mix manifest.json && cp mix.mp3 out/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import Measurements, SourceMeasure, collect_measurements, collect_single_file_measurements
from .checks import (
    STANDALONE_CHECKS,
    VerifyConfig,
    run_all_checks,
)
from .manifest import ManifestError, load_manifest
from .report import build_report

_AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".aiff", ".aac", ".ogg", ".m4a", ".wma"})


def _is_json(path: Path) -> bool:
    return path.suffix.lower() == ".json"


def _is_audio(path: Path) -> bool:
    return path.suffix.lower() in _AUDIO_EXTENSIONS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_mix",
        description="Verify an assembled mix against its build manifest.",
    )
    parser.add_argument("target", type=Path, help="build-plan JSON manifest or audio file")
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        metavar="PATH",
        help="also write the full report as JSON to PATH ('-' for stdout)",
    )
    parser.add_argument(
        "--pre-only",
        action="store_true",
        help="run only pre-render checks (sources + manifest, no output file)",
    )
    args = parser.parse_args(argv)

    config = VerifyConfig()

    if _is_json(args.target):
        # manifest mode
        try:
            manifest = load_manifest(args.target)
        except ManifestError as exc:
            print(f"mix-verify: FAIL: {exc}", file=sys.stderr)
            return 2

        measurements = collect_measurements(
            manifest,
            min_bpm=config.min_bpm,
            max_bpm=config.max_bpm,
            min_segment_s=config.min_segment_s,
            skip_output=args.pre_only,
        )
        results = run_all_checks(manifest, measurements, config, skip_post=args.pre_only)
        report = build_report(str(manifest.output), results)
    elif _is_audio(args.target):
        # standalone audio mode
        out = collect_single_file_measurements(
            args.target,
            min_bpm=config.min_bpm,
            max_bpm=config.max_bpm,
        )
        if not out.exists:
            print(f"mix-verify: FAIL: file not found: {args.target}", file=sys.stderr)
            return 2

        measurements = Measurements(backbone=SourceMeasure(path=args.target), output=out)
        results = run_all_checks(None, measurements, config, checks_override=STANDALONE_CHECKS)
        report = build_report(str(args.target), results)
    else:
        print(
            f"mix-verify: FAIL: unrecognized file type: {args.target.suffix} "
            f"(expected .json or audio file)",
            file=sys.stderr,
        )
        return 2

    print(report.to_text())
    if args.json is not None:
        if str(args.json) == "-":
            print(report.to_json())
        else:
            args.json.write_text(report.to_json() + "\n", encoding="utf-8")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
