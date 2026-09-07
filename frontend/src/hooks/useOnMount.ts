import { useEffect, useRef } from "react";

export const useOnMount = (fn: () => void, deps: any[] = []) => {
  const isMounting = useRef<boolean>(true);
  useEffect(() => {
    if (isMounting.current) {
      isMounting.current = false;
      return fn();
    }
  }, deps);
};
