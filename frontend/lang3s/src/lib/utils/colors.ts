import { AnnotationColors } from "@/features/common/constants";

const COLORS = [
  ...Object.keys(AnnotationColors).filter((k) => k !== "SKYBLUE"),
  "sky",
];

export const getColorName = (name: string, colors: string[] = COLORS) => {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % colors.length;
  return colors[index];
};
