from __future__ import annotations

import argparse
import json
from pathlib import Path

from .collector import collect, collect_contests
from .evaluator import evaluate, render_eligibility_report, render_report
from .extractor import extract_manifest
from .web_seed import convert_records


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_artifacts(root: Path, manifest: dict, suffix: str, renderer) -> None:
    records = extract_manifest(manifest, root)
    dump(root / f"extracted{suffix}.json", records)
    metrics = evaluate(records, root)
    dump(root / f"metrics{suffix}.json", metrics)
    (root / f"report{suffix}.md").write_text(renderer(metrics, manifest), encoding="utf-8")


def run(root: Path) -> dict:
    manifest = collect(root)
    dump(root / "manifest.json", manifest)
    _write_artifacts(root, manifest, "", render_report)
    return manifest


def run_eligibility(root: Path) -> dict:
    existing_manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest = collect_contests(root, existing_manifest)
    dump(root / "manifest_eligibility.json", manifest)
    _write_artifacts(root, manifest, "_eligibility", render_eligibility_report)
    return manifest


def build_web_seed(root: Path) -> dict:
    records = json.loads((root / "extracted_eligibility.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest_eligibility.json").read_text(encoding="utf-8"))
    seed = convert_records(records, manifest["collected_at"])
    target = root / "web" / "data" / "seed.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    dump(target, seed)
    return seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Linkareer 공고 속성 추출 검증 프로토타입")
    parser.add_argument("--output", type=Path, default=Path.cwd())
    parser.add_argument("--eligibility", action="store_true", help="공모전 자격 판정 검증을 실행")
    parser.add_argument("--web-seed-only", action="store_true", help="기존 30건으로 웹 seed.json만 생성")
    args = parser.parse_args()
    if args.web_seed_only:
        seed = build_web_seed(args.output.resolve())
        print(json.dumps({"contests": len(seed["contests"])}, ensure_ascii=False))
        return
    manifest = run_eligibility(args.output.resolve()) if args.eligibility else run(args.output.resolve())
    print(json.dumps({"counts": manifest["counts"], "requests": manifest["request_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

