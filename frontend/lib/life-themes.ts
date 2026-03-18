export interface LifeTheme {
  id: string;
  label: string;
  icon: string;
  description: string;
  longDescription: string;
  lawIds: string[];
}

// Law ID constants
const CIVIL_CODE = "129AC0000000089";
const APPI = "415AC0000000057";
const ROAD_TRAFFIC = "335AC0000000105";
const LABOR_STANDARDS = "322AC0000000049";
const COPYRIGHT = "345AC0000000048";

export const LIFE_THEMES: LifeTheme[] = [
  {
    id: "marriage",
    label: "結婚・離婚",
    icon: "family_restroom",
    description: "婚姻届、離婚、親権、養育費など",
    longDescription:
      "婚姻・離婚の手続き、親権の行使、養育費、面会交流など、家族関係に関わる法律の改正を追えます。",
    lawIds: [CIVIL_CODE],
  },
  {
    id: "parenting",
    label: "子育て",
    icon: "family_restroom",
    description: "親権、養育、児童福祉、育児休業など",
    longDescription:
      "親権制度、嫡出推定、認知、育児休業など、子育てに関わる法律の改正を追えます。",
    lawIds: [CIVIL_CODE, LABOR_STANDARDS],
  },
  {
    id: "work",
    label: "働く・転職",
    icon: "work",
    description: "労働時間、残業、解雇、有給休暇など",
    longDescription:
      "労働時間の上限、残業代、有給休暇、育児介護休業など、働く人の権利に関わる法律の改正を追えます。",
    lawIds: [LABOR_STANDARDS],
  },
  {
    id: "driving",
    label: "車・運転",
    icon: "speed",
    description: "免許、交通違反、自転車ルールなど",
    longDescription:
      "運転免許の取得条件、交通違反の罰則、自転車のルール、あおり運転規制など、交通に関わる法律の改正を追えます。",
    lawIds: [ROAD_TRAFFIC],
  },
  {
    id: "privacy",
    label: "個人情報",
    icon: "lock",
    description: "個人データの取り扱い、プライバシーなど",
    longDescription:
      "個人情報の収集・利用ルール、データの第三者提供、オプトアウト制度など、プライバシーに関わる法律の改正を追えます。",
    lawIds: [APPI],
  },
  {
    id: "inheritance",
    label: "相続",
    icon: "description",
    description: "遺言、相続分、遺産分割など",
    longDescription:
      "法定相続分、遺言の方式、遺産分割、特別寄与料など、相続に関わる法律の改正を追えます。",
    lawIds: [CIVIL_CODE],
  },
  {
    id: "creative",
    label: "著作権・創作",
    icon: "description",
    description: "著作物の利用、引用、SNS投稿、AI学習など",
    longDescription:
      "著作権の保護範囲、引用のルール、デジタルコンテンツの利用、AI学習データの取り扱いなど、創作活動に関わる法律の改正を追えます。",
    lawIds: [COPYRIGHT],
  },
];

export function getThemeById(id: string): LifeTheme | undefined {
  return LIFE_THEMES.find((t) => t.id === id);
}

export function getThemesForLaw(lawId: string): LifeTheme[] {
  return LIFE_THEMES.filter((t) => t.lawIds.includes(lawId));
}
