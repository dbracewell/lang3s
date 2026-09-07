export const remap = (
  value: number,
  old_min: number,
  old_max: number,
  new_min: number,
  new_max: number,
) => {
  return (
    ((value - old_min) * (new_max - new_min)) / (old_max - old_min) + new_min
  );
};
