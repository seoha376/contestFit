export const APP_CONFIG = Object.freeze({
  confidenceThreshold: 0.7,
  storageKey: "contest-fit.profile.v1",
  filters: [
    { id: "all", label: "전체" },
    { id: "eligible", label: "가능" },
    { id: "needs_review", label: "확인 필요" },
    { id: "ineligible", label: "불가" },
  ],
  statusOptions: ["재학생", "휴학생", "대학원생", "수료생", "직장인", "일반인", "예비창업자"],
  nationalityOptions: ["대한민국", "외국인"],
  regionOptions: ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"],
  businessOptions: [
    { value: "none", label: "사업자 없음" },
    { value: "prospective", label: "예비창업자" },
    { value: "registered", label: "사업자 보유" },
  ],
  entryOptions: [
    { value: "individual", label: "개인" },
    { value: "team", label: "팀" },
  ],
  skillGroups: [
    { name: "개발·데이터", skills: ["Python", "JavaScript", "앱 개발", "웹 개발", "데이터 분석", "AI 활용"] },
    { name: "디자인·콘텐츠", skills: ["UI/UX 디자인", "그래픽 디자인", "영상 편집", "사진 촬영", "글쓰기", "발표"] },
    { name: "기획·연구", skills: ["서비스 기획", "아이디어 발상", "시장 조사", "사용자 조사", "문제 해결", "보고서 작성"] },
    { name: "사업·협업", skills: ["창업", "마케팅", "브랜딩", "프로젝트 관리", "팀 협업", "영어"] },
  ],
  interestOptions: ["AI", "데이터", "개발", "디자인", "환경", "관광", "창업", "영상", "사진", "글쓰기"],
});

export const EMPTY_PROFILE = Object.freeze({
  status: "",
  nationality: "",
  age: "",
  affiliation: "",
  school: "",
  skills: [],
  interests: [],
  region: "",
  schoolRegion: "",
  affiliationRegion: "",
  businessStatus: "",
  businessYears: "",
  entryType: "",
  teamSize: "",
  selectedSectionId: "",
});

export const REPRESENTATIVE_PROFILES = Object.freeze([
  {
    name: "24세 서울 재학생·개인",
    profile: { status: "재학생", nationality: "대한민국", age: 24, affiliation: "일반 전공", region: "서울", businessStatus: "none", businessYears: null, entryType: "individual", teamSize: 1 },
  },
  {
    name: "29세 직장인·개인",
    profile: { status: "직장인", nationality: "대한민국", age: 29, affiliation: "직장인", region: "서울", businessStatus: "none", businessYears: null, entryType: "individual", teamSize: 1 },
  },
  {
    name: "22세 휴학생·3인 팀",
    profile: { status: "휴학생", nationality: "대한민국", age: 22, affiliation: "일반 전공", region: "서울", businessStatus: "none", businessYears: null, entryType: "team", teamSize: 3 },
  },
  {
    name: "35세 사업자·개인",
    profile: { status: "일반인", nationality: "대한민국", age: 35, affiliation: "사업자", region: "경기", businessStatus: "registered", businessYears: 4, entryType: "individual", teamSize: 1 },
  },
]);
