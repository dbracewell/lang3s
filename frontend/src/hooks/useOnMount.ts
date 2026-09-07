import { useEffect, useRef } from "react";

export const useOnMount = (fn: () => void) => {
  const fnRef = useRef(fn);

  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    fnRef.current();
  }, []);
};
