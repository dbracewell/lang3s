import { useTRPC } from "@/lib/trpc/client";
import { AppRouter } from "@/lib/trpc/routers/_app";
import {
  QueryClient,
  useMutation,
  UseMutationOptions,
  UseMutationResult,
  useQueryClient,
} from "@tanstack/react-query";
import { TRPCOptionsProxy } from "@trpc/tanstack-react-query";
import { toast } from "sonner";

export function useTRPCMutation<
  TData = unknown,
  TError = unknown,
  TVariables = void,
  TContext = unknown,
>(
  getOptions: (
    client: TRPCOptionsProxy<AppRouter>,
    queryClient: QueryClient,
  ) => {
    mutation: UseMutationOptions<TData, TError, TVariables, TContext>;
    successToast?: string;
    errorToast?: string;
  },
): UseMutationResult<TData, TError, TVariables, TContext> {
  const client = useTRPC();
  const queryClient = useQueryClient();
  const { mutation, successToast, errorToast } = getOptions(
    client,
    queryClient,
  );

  const optionsOnSuccess = mutation.onSuccess;
  const optionsOnError = mutation.onError;

  if (successToast) {
    mutation.onSuccess = (data, variables, onMutationResult, context) => {
      optionsOnSuccess?.(data, variables, onMutationResult, context);
      toast.success(successToast);
    };
  }

  if (errorToast) {
    mutation.onError = (error, variables, onMutationResult, context) => {
      optionsOnError?.(error, variables, onMutationResult, context);
      toast.error(errorToast);
    };
  }

  return useMutation(mutation);
}
