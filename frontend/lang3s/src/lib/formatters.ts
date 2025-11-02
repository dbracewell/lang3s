export const capitalize = (text: string, allWords: boolean = false): string => {
  if (!text?.trim()) {
    return "";
  }
  console.log(text);
  return text
    .split(/[\s_]+/g)
    .filter((s) => s != null && s !== undefined && s !== "")
    .map((word, idx) => {
      if (allWords || idx === 0) {
        return word[0].toUpperCase() + word.slice(1);
      }
      return word;
    })
    .join(" ");
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
  searchParams: Record<string, string | number | boolean | null | undefined>,
) => {
  const paramBuilder = new URLSearchParams();
  Object.entries(searchParams).forEach(([k, v]) => {
    if (v != null) {
      const strValue = String(v);
      if (!!strValue.trim()) {
        paramBuilder.set(k, strValue.trim());
      }
    }
  });
  return `${path}/?${paramBuilder.toString()}`;
};
