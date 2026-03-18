export interface LifeTheme {
  id: string;
  label: string;
  icon: string; // Material Symbols icon name
  description: string;
  lawIds: string[];
}

export const LIFE_THEMES: LifeTheme[] = [
  {
    id: "marriage",
    label: "結婚・離婚",
    icon: "family_restroom",
    description: "婚姻届、離婚、親権、養育費など",
    lawIds: ["129AC0000000089"],
  },
  {
    id: "parenting",
    label: "子育て",
    icon: "family_restroom",
    description: "親権、養育、児童福祉、育児休業など",
    lawIds: ["129AC0000000089"],
  },
  {
    id: "work",
    label: "働く・転職",
    icon: "work",
    description: "労働時間、残業、解雇、有給休暇など",
    lawIds: ["322AC0000000049"],
  },
  {
    id: "driving",
    label: "車・運転",
    icon: "speed",
    description: "免許、交通違反、自転車ルールなど",
    lawIds: ["335AC0000000105"],
  },
  {
    id: "privacy",
    label: "個人情報",
    icon: "lock",
    description: "個人データの取り扱い、プライバシーなど",
    lawIds: ["415AC0000000057"],
  },
  {
    id: "inheritance",
    label: "相続",
    icon: "description",
    description: "遺言、相続分、遺産分割など",
    lawIds: ["129AC0000000089"],
  },
];

export function getThemesForLaw(lawId: string): LifeTheme[] {
  return LIFE_THEMES.filter((t) => t.lawIds.includes(lawId));
}
