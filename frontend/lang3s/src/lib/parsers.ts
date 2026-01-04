import { createParser } from "nuqs";

export const parsePageIndex = createParser({
  parse(queryValue) {
    const p = Number(queryValue);
    if (Number.isNaN(p) || p < 1) return 1;
    return p;
  },
  serialize(value) {
    return String(value);
  },
});
