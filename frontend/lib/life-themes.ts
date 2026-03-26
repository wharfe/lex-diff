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
const PENAL_CODE = "140AC0000000045";
const CONSUMER_CONTRACT = "412AC0000000061";
const CHILDCARE_LEAVE = "403AC0000000076";
const BUILDING_STANDARDS = "325AC0000000201";
const REAL_PROPERTY_REG = "416AC0000000123";
const MY_NUMBER = "425AC0000000027";
const INFO_PLATFORM = "413AC0000000137";

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
    lawIds: [CIVIL_CODE, LABOR_STANDARDS, CHILDCARE_LEAVE],
  },
  {
    id: "work",
    label: "働く・転職",
    icon: "work",
    description: "労働時間、残業、解雇、有給休暇、育休など",
    longDescription:
      "労働時間の上限、残業代、有給休暇、育児介護休業など、働く人の権利に関わる法律の改正を追えます。",
    lawIds: [LABOR_STANDARDS, CHILDCARE_LEAVE],
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
    lawIds: [CIVIL_CODE, REAL_PROPERTY_REG],
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
  {
    id: "crime",
    label: "犯罪・刑罰",
    icon: "gavel",
    description: "性犯罪、侮辱罪、詐欺、刑罰の重さなど",
    longDescription:
      "不同意性交等罪の新設、侮辱罪の厳罰化、詐欺・窃盗の罰則など、刑事法の改正を追えます。",
    lawIds: [PENAL_CODE],
  },
  {
    id: "shopping",
    label: "消費・契約",
    icon: "shopping_cart",
    description: "悪質商法、サブスク解約、ネット通販トラブルなど",
    longDescription:
      "不当な勧誘への取消権、サブスクリプション解約ルール、ネット通販トラブルなど、消費者を守る法律の改正を追えます。",
    lawIds: [CONSUMER_CONTRACT],
  },
  {
    id: "housing",
    label: "住まい・建築",
    icon: "home",
    description: "省エネ基準、建築確認、リフォーム規制など",
    longDescription:
      "建築物の省エネルギー基準、建築確認手続き、耐震基準、リフォーム規制など、住まいに関わる法律の改正を追えます。",
    lawIds: [BUILDING_STANDARDS, REAL_PROPERTY_REG],
  },
  {
    id: "mynumber",
    label: "マイナンバー",
    icon: "badge",
    description: "マイナカード、保険証、行政手続きなど",
    longDescription:
      "マイナンバーカードの利用範囲、健康保険証との一体化、行政手続きのデジタル化など、番号制度に関わる法律の改正を追えます。",
    lawIds: [MY_NUMBER],
  },
  {
    id: "sns",
    label: "ネット・SNS",
    icon: "forum",
    description: "誹謗中傷、発信者開示、プラットフォーム規制など",
    longDescription:
      "SNS上の誹謗中傷への対処、発信者情報の開示請求、大規模プラットフォームの透明性義務など、インターネット利用に関わる法律の改正を追えます。",
    lawIds: [INFO_PLATFORM],
  },
];

export function getThemeById(id: string): LifeTheme | undefined {
  return LIFE_THEMES.find((t) => t.id === id);
}

export function getThemesForLaw(lawId: string): LifeTheme[] {
  return LIFE_THEMES.filter((t) => t.lawIds.includes(lawId));
}
