export const capitalize = (text: string, allWords: boolean = false): string => {
  if (!text?.trim()) {
    return "";
  }
  return text
    .split(/[\s_]+/g)
    .filter((s) => s != null && true && s !== "")
    .map((word, idx) => {
      if (allWords || idx === 0) {
        return word[0].toUpperCase() + word.slice(1).toLowerCase();
      }
      return word;
    })
    .join(" ");
};

export const truncateText = (text: string, maxLength = 35) => {
  if (text.length <= maxLength) return text;
  const truncated = text.substring(0, text.lastIndexOf(" ", maxLength));
  return `${truncated || text.substring(0, maxLength)}...`;
};

export const formatDuration = (milliseconds: number): string => {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const pad = (num: number) => num.toString().padStart(2, "0");

  if (hours > 0) {
    return `${hours}:${pad(minutes)}:${pad(seconds)}`;
  } else {
    return `${minutes}:${pad(seconds)}`;
  }
};

export const formatURL = (
  path: string,
  searchParams: Record<
    string,
    string | number | boolean | null | undefined | string[] | number[]
  >,
) => {
  const paramBuilder = new URLSearchParams();
  Object.entries(searchParams).forEach(([k, v]) => {
    if (v != null) {
      const strValue = Array.isArray(v)
        ? v.map((e) => String(e)).join(",")
        : String(v);
      if (!!strValue.trim()) {
        paramBuilder.set(k, strValue.trim());
      }
    }
  });
  return `${path}/?${paramBuilder.toString()}`;
};

export const formatNumber = (num: number) => {
  return new Intl.NumberFormat(undefined, {
    notation: "standard",
    compactDisplay: "long",
    style: "decimal",
    maximumFractionDigits: 2,
  }).format(num);
};

export const formatCount = (
  count: number,
  { single, plural }: { single: string; plural: string },
) => {
  if (count === 1) {
    return `${count} ${single}`;
  }
  return `${count} ${plural}`;
};
