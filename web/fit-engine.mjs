// Topic affinity is an exploration aid. Eligibility remains in decision-engine.mjs.
const TOPIC_ALIASES = [
  ["AI", ["AI", "인공지능", "머신러닝", "딥러닝", "생성형"]],
  ["데이터", ["데이터", "빅데이터", "통계", "분석"]],
  ["개발", ["개발", "프로그래밍", "코딩", "소프트웨어", "앱", "웹서비스"]],
  ["디자인", ["디자인", "UX", "UI", "시각"]],
  ["영상", ["영상", "비디오", "영화", "숏폼"]],
  ["사진", ["사진", "포토", "촬영"]],
  ["글쓰기", ["글쓰기", "수필", "시문학", "문학", "스토리"]],
  ["창업", ["창업", "스타트업", "비즈니스"]],
  ["환경", ["환경", "기후", "탄소", "ESG"]],
  ["관광", ["관광", "여행", "지역문화"]],
  ["공공", ["공공", "행정", "정책", "사회문제"]],
];

const SKILL_TOPIC_HINTS = new Map([
  ["AI 활용", "AI"], ["데이터 분석", "데이터"], ["앱 개발", "개발"], ["웹 개발", "개발"],
  ["UI/UX 디자인", "디자인"], ["그래픽 디자인", "디자인"], ["영상 편집", "영상"],
  ["사진 촬영", "사진"], ["글쓰기", "글쓰기"], ["창업", "창업"],
]);

function normalized(value) {
  return String(value ?? "").normalize("NFKC").trim().toLocaleLowerCase("ko-KR").replace(/\s+/g, " ");
}

function canonical(value) {
  const name = normalized(value);
  for (const [tag, aliases] of TOPIC_ALIASES) {
    if (aliases.some((alias) => normalized(alias) === name)) return tag;
  }
  return name;
}

function values(input) {
  const items = Array.isArray(input) ? input : String(input ?? "").split(/[,，\n]/);
  return [...new Set(items.map((item) => String(item).trim()).filter(Boolean))];
}

export function titleTopics(title) {
  const source = normalized(title);
  return TOPIC_ALIASES.filter(([, aliases]) => aliases.some((alias) => {
    const word = normalized(alias);
    if (word === "ai" || word === "ux" || word === "ui" || word === "esg") {
      return new RegExp(`(?:^|[^a-z])${word}(?:$|[^a-z])`, "i").test(source);
    }
    return source.includes(word);
  })).map(([tag]) => tag);
}

export function evaluateFit(contest, profile) {
  const explicitTopics = values(contest.topic_tags);
  const topics = explicitTopics.length ? explicitTopics : titleTopics(contest.title);
  const topicSource = explicitTopics.length ? "검수한 공고 주제" : "공고 제목";
  const skills = (Array.isArray(contest.skill_signals) ? contest.skill_signals : [])
    .filter((item) => item && typeof item.name === "string" && String(item.evidence ?? "").trim());
  const selectedSkills = values(profile.skills);
  const userTopics = new Set([...selectedSkills, ...values(profile.interests)].map(canonical));
  const skillTopics = new Set(selectedSkills.map((skill) => SKILL_TOPIC_HINTS.get(skill)).filter(Boolean).map(canonical));
  const userSkills = new Set(values(profile.skills).map(canonical));
  const matchedTopics = topics.filter((topic) => userTopics.has(canonical(topic)) || skillTopics.has(canonical(topic)));
  const matchedSkillTopics = matchedTopics.filter((topic) => skillTopics.has(canonical(topic)) && !userTopics.has(canonical(topic)));
  const matchedInterestTopics = matchedTopics.filter((topic) => !matchedSkillTopics.includes(topic));
  const matchedSkills = skills.filter((item) => userSkills.has(canonical(item.name))).map((item) => item.name);
  const reasons = [];
  if (matchedInterestTopics.length) reasons.push(`${topicSource}의 ${matchedInterestTopics.join(", ")}와 입력한 관심·역량 키워드가 일치합니다.`);
  if (matchedSkillTopics.length) reasons.push(`${topicSource}의 주제(${matchedSkillTopics.join(", ")})와 선택한 역량 분야가 연결됩니다. 실제 요구 역량은 원문을 확인하세요.`);
  if (matchedSkills.length) reasons.push(`공고 근거에 나온 ${matchedSkills.join(", ")}와 입력한 역량이 일치합니다.`);
  const hasSource = topics.length || skills.length;
  const hasProfile = userTopics.size > 0 || skillTopics.size > 0;
  const level = !hasSource || !hasProfile ? "unknown" : reasons.length ? "related" : "no_signal";
  if (level === "unknown") reasons.push(!hasProfile ? "관심 분야나 역량을 입력하면 관련 키워드를 비교합니다." : "공고에 비교할 주제·역량 정보가 부족합니다.");
  if (level === "no_signal") reasons.push("입력한 키워드와 확인된 공고 키워드가 일치하지 않습니다. 지원 자격과는 별개입니다.");
  return { level, topics, topicSource, matchedTopics, matchedSkills, reasons };
}
