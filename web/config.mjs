export const APP_CONFIG = Object.freeze({
  apiBaseUrl: "http://localhost:8080/api",
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
});

export const EMPTY_PROFILE = Object.freeze({
  status: "",
  nationality: "",
  age: "",
  affiliation: "",
  region: "",
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
