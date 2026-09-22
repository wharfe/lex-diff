/** "2026-09-22" -> "2026年9月22日".
 *
 * Built from the string rather than through Date: a date-only string parses as
 * UTC midnight, so a build running west of Greenwich would render the day
 * before -- and the day is the whole claim this page makes about its text.
 */
export function jpDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${Number(y)}年${Number(m)}月${Number(d)}日`;
}
