import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { judgeContest } from "../web/decision-engine.mjs";

const [, , casesPath, dataPath = "web/data/curated.json"] = process.argv;
if (!casesPath) {
  console.error("사용법: node scripts/evaluate.mjs <수기정답.json> [공고데이터.json]");
  process.exit(2);
}

const cases = JSON.parse(readFileSync(resolve(casesPath), "utf8"));
const contests = JSON.parse(readFileSync(resolve(dataPath), "utf8")).contests;
if (!Array.isArray(cases) || !cases.length || !Array.isArray(contests)) {
  throw new Error("정답 사례 배열과 공고 데이터가 필요합니다.");
}
const byId = new Map(contests.map((item) => [item.id, item]));
const labels = ["eligible", "needs_review", "ineligible"];
const confusion = Object.fromEntries(labels.map((expected) => [expected, Object.fromEntries(labels.map((actual) => [actual, 0]))]));
let correct = 0;
let falseEligible = 0;
let predictedEligible = 0;
for (const [index, row] of cases.entries()) {
  const contest = byId.get(row.contest_id);
  if (!contest || !labels.includes(row.expected) || !row.profile || typeof row.profile !== "object") {
    throw new Error(`${index + 1}번째 정답 사례의 공고 ID, 프로필 또는 정답을 확인해 주세요.`);
  }
  const actual = judgeContest(contest, row.profile).result;
  confusion[row.expected][actual] += 1;
  if (actual === row.expected) correct += 1;
  if (actual === "eligible") {
    predictedEligible += 1;
    if (row.expected !== "eligible") falseEligible += 1;
  }
}
console.log(JSON.stringify({
  cases: cases.length,
  correct,
  accuracy: correct / cases.length,
  false_eligible: falseEligible,
  false_eligible_rate: predictedEligible ? falseEligible / predictedEligible : null,
  predicted_eligible: predictedEligible,
  confusion,
}, null, 2));
