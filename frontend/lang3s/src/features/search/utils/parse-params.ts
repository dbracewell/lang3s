import { ParsedSearchParams } from "@/features/search/schemas";

export const toSearchParams = (searchParams: ParsedSearchParams) => {
  const params = new URLSearchParams();

  Object.entries(searchParams).forEach(([k, v]) => {
    if (v == null) return;
    if (typeof v === "string") {
      if (!!v.trim()) {
        params.set(k, String(v));
      }
    } else if (typeof v === "boolean" && v) {
      params.set(k, String(v));
    } else if (typeof v === "number" && v != 0) {
      params.set(k, String(v));
    } else {
      params.set(k, String(v));
    }
  });

  return params.toString();
};
