import { RefObject, useCallback, useMemo, useRef } from "react";
import * as d3 from "d3";
import { getTypeBoundsFn } from "@/components/d3/types";

export const useRegistry = ({
  externalRefs,
}: {
  externalRefs?: Record<string, RefObject<any | null>>;
}) => {
  const registry = useRef<Record<string, RefObject<any>>>({});
  const nullRef = useRef(null);

  const registerRef = useCallback((name: string, ref: RefObject<any>) => {
    registry.current[name] = ref;
  }, []);

  const getRef = useCallback(
    (name: string) => {
      if (externalRefs != null && externalRefs[name] != null) {
        return externalRefs[name] ?? nullRef;
      }
      return registry.current[name] ?? nullRef;
    },
    [externalRefs],
  );

  return { getRef, registerRef };
};

export const useFindMinMaxValue = <V>({
  data,
  getValue,
}: {
  data?: V[];
  getValue: (o: V) => number;
}): { minValue: number; maxValue: number } => {
  const { minValue, maxValue } = useMemo(() => {
    if (data == null || !data.length) return { minValue: 0, maxValue: 0 };
    let minValue = getValue(data[0]);
    let maxValue = getValue(data[0]);
    data.forEach((point) => {
      const pointValue = getValue(point);
      maxValue = Math.max(maxValue, Math.min(minValue, pointValue));
      minValue = Math.min(minValue, Math.min(maxValue, pointValue));
    });
    return { minValue, maxValue };
  }, [data, getValue]);
  return { minValue, maxValue };
};

export const useLinearScaler = ({
  valueRanges,
  minValue,
  maxValue,
}: {
  valueRanges?: { minValue: number; maxValue: number };
  minValue: number;
  maxValue: number;
}) => {
  return useMemo(() => {
    if (valueRanges == null) {
      return null;
    }
    return d3.scaleLinear(
      [valueRanges.minValue, valueRanges.maxValue],
      [minValue, maxValue],
    );
  }, [valueRanges, minValue, maxValue]);
};

export const useFindMultiTypeMinMaxValue = <V>({
  points,
  getType,
  getValue,
}: {
  points?: V[];
  getType: (o: V) => string;
  getValue: (o: V) => number;
}): Record<string, { max: number; min: number }> | undefined => {
  return useMemo(() => {
    if (points == null || !points.length) return undefined;
    let values: Record<string, { min: number; max: number }> = {};
    points.forEach((point) => {
      const value = getValue(point);
      const type = getType(point);
      if (values[type] == null) {
        values[type] = { min: Number.MAX_VALUE, max: Number.MIN_VALUE };
      }
      values[type] = {
        max: Math.max(values[type].max, value),
        min: Math.min(values[type].min, value),
      };
    });
    return values;
  }, [getType, getValue, points]);
};

const getScaler = (scale_type?: "linear" | "log") => {
  if (scale_type == null || scale_type.trim() === "linear")
    return d3.scaleLinear;
  return d3.scaleLog;
};

export const useMultiTypeLinearScaler = ({
  valueRanges,
  getTypeBounds,
  scalers,
}: {
  valueRanges?: Record<string, { max: number; min: number }>;
  getTypeBounds: getTypeBoundsFn;
  scalers?: Record<string, "linear" | "log">;
}) => {
  return useMemo(() => {
    if (valueRanges == null) return undefined;
    const entries = Object.entries(valueRanges);
    return Object.fromEntries(
      entries.map(([type, minmax]) => [
        type,
        getScaler(scalers?.[type])(
          [minmax.min, minmax.max],
          [
            getTypeBounds({ type, bound: "min" }),
            getTypeBounds({ type, bound: "max" }),
          ],
        ),
      ]),
    );
  }, [valueRanges, scalers, getTypeBounds]);
};
