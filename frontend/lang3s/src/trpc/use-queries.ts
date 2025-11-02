import {
  useInfiniteQuery,
  UseInfiniteQueryOptions,
  UseInfiniteQueryResult,
  useQuery,
  UseQueryOptions,
  UseQueryResult,
  useSuspenseInfiniteQuery,
  UseSuspenseInfiniteQueryOptions,
  UseSuspenseInfiniteQueryResult,
  useSuspenseQuery,
  UseSuspenseQueryOptions,
  UseSuspenseQueryResult,
} from "@tanstack/react-query";
import { useTRPC } from "@/trpc/client";
import { TRPCOptionsProxy } from "@trpc/tanstack-react-query";
import { AppRouter } from "@/trpc/routers/_app";

export function useTRPCQuery<
  TQueryFnData = unknown,
  TError = unknown,
  TData = TQueryFnData,
  TQueryKey extends readonly unknown[] = unknown[],
>(
  getOptions: (
    client: TRPCOptionsProxy<AppRouter>,
  ) => UseQueryOptions<TQueryFnData, TError, TData, TQueryKey>,
): UseQueryResult<TData, TError> {
  const client = useTRPC();
  const options = getOptions(client);
  return useQuery(options);
}

export function useTRPCSuspenseQuery<
  TQueryFnData = unknown,
  TError = unknown,
  TData = TQueryFnData,
  TQueryKey extends readonly unknown[] = unknown[],
>(
  getOptions: (
    client: TRPCOptionsProxy<AppRouter>,
  ) => UseSuspenseQueryOptions<TQueryFnData, TError, TData, TQueryKey>,
): UseSuspenseQueryResult<TData, TError> {
  const client = useTRPC();
  const options = getOptions(client);
  return useSuspenseQuery(options);
}

export function useTRPCInfiniteQuery<
  TQueryFnData = unknown,
  TError = unknown,
  TData = TQueryFnData,
  TQueryKey extends readonly unknown[] = unknown[],
  TPageParam = unknown,
>(
  getOptions: (
    client: TRPCOptionsProxy<AppRouter>,
  ) => UseInfiniteQueryOptions<
    TQueryFnData,
    TError,
    TData,
    TQueryKey,
    TPageParam
  >,
): UseInfiniteQueryResult<TData, TError> {
  const client = useTRPC();
  const options = getOptions(client);
  return useInfiniteQuery(options);
}

export function useTRPCSuspenseInfiniteQuery<
  TQueryFnData = unknown,
  TError = unknown,
  TData = TQueryFnData,
  TQueryKey extends readonly unknown[] = unknown[],
  TPageParam = unknown,
>(
  getOptions: (
    client: TRPCOptionsProxy<AppRouter>,
  ) => UseSuspenseInfiniteQueryOptions<
    TQueryFnData,
    TError,
    TData,
    TQueryKey,
    TPageParam
  >,
): UseSuspenseInfiniteQueryResult<TData, TError> {
  const client = useTRPC();
  const options = getOptions(client);
  return useSuspenseInfiniteQuery(options);
}
