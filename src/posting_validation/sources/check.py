"""Live check of every official API: ``python -m posting_validation.sources.check``.

Prints one row per source (status, count, latency, sample title) and writes the
same table to $GITHUB_STEP_SUMMARY when it runs in GitHub Actions. Exits 1 when
a source with a configured key fails or when fewer than ``--min-ok`` sources
answer. Keys are read from the environment and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import CONTEST_SOURCES, careernet, clear_cache, collect, configured, env, http


def run(min_ok: int) -> int:
    clear_cache()
    values = env()
    result = collect(store=None)
    by_id = {item["id"]: item for item in result["sources"]}
    rows, failures = [], []
    for module in CONTEST_SOURCES:
        source = module.SOURCE
        status = by_id.get(source["id"], {"status": "not_configured", "count": 0})
        sample = next((contest["title"] for contest in result["contests"] if contest["id"].startswith(source["id"] + "-")), "")
        rows.append((source["name"], status["status"], status.get("count", 0), status.get("elapsed_ms", "-"), status.get("error", "") or sample[:40]))
        if configured(module, values) and status["status"] != "ok":
            failures.append(source["name"])
    major_status = "not_configured"
    if configured(careernet, values):
        try:
            majors = careernet.search(values, "컴퓨터")
            major_status = f"ok ({len(majors)}건)"
        except http.SourceError as exc:
            major_status = f"error: {exc}"
            failures.append(careernet.SOURCE["name"])
    rows.append((careernet.SOURCE["name"], major_status, "-", "-", "학과 계열 조회 '컴퓨터'"))
    ok = sum(1 for row in rows if str(row[1]).startswith("ok"))
    lines = ["| 출처 | 상태 | 건수 | 응답(ms) | 예시/오류 |", "|---|---|---:|---:|---|"]
    lines += [f"| {name} | {status} | {count} | {elapsed} | {note} |" for name, status, count, elapsed, note in rows]
    lines.append(f"\n모드: `{http.mode()}` · 응답 출처 {ok}개 · 공고 {len(result['contests'])}건")
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("## 공식 API 실호출 점검\n\n" + report + "\n")
    with open(os.environ.get("CONTESTFIT_CHECK_OUTPUT", "test-results/source-check.json"), "w", encoding="utf-8") as stream:
        json.dump({"sources": result["sources"], "contests": len(result["contests"]), "ok": ok, "failures": failures},
                  stream, ensure_ascii=False, indent=2)
    if failures:
        print(f"실패한 출처: {', '.join(failures)}", file=sys.stderr)
        return 1
    if ok < min_ok:
        print(f"응답한 출처가 {ok}개로 기준 {min_ok}개보다 적습니다.", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Call every configured official API once and report")
    parser.add_argument("--min-ok", type=int, default=1)
    args = parser.parse_args()
    os.makedirs("test-results", exist_ok=True)
    sys.exit(run(args.min_ok))


if __name__ == "__main__":
    main()
