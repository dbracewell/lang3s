export const truncateLabel = (label: string, length: number) => {
  if (label.length <= length) {
    return label;
  }
  return label.substring(0, length) + "...";
};
