import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { useCallback, useEffect, useState } from "react";
import { useTRPCMutation } from "@/lib/trpc/use-mutation";

type SetValueType<T> = (value: T, persist?: boolean) => void;

const useConfigValue = <T>(
  name: string,
  defaultValue: T,
): [T, SetValueType<T>] => {
  const [value, setValue] = useState<T>(defaultValue);

  const { data, refetch } = useTRPCQuery((trpc) =>
    trpc.config.getValue.queryOptions({ name }, { staleTime: 1 }),
  );

  const updateValue = useTRPCMutation((trpc) => ({
    mutation: trpc.config.setValue.mutationOptions({
      onSuccess: () => refetch(),
    }),
  }));

  useEffect(() => {
    if (data != null) {
      setValue(data as T);
    } else {
      setValue(defaultValue);
    }
  }, [defaultValue, data]);

  const setNewValue = useCallback(
    (newValue: T, persist: boolean = false) => {
      setValue(newValue);
      if (persist) {
        updateValue.mutate({ name, value: newValue });
      } else {
        refetch();
      }
    },
    [name, setValue, refetch],
  );

  return [value, setNewValue];
};
export default useConfigValue;
