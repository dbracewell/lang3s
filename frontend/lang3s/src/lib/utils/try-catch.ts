import { TRPCError } from "@trpc/server";

interface Options<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
  logError?: string;
}

type Success<T> = {
  data: T;
  isError: false;
};

type Failure = {
  data: null;
  isError: true;
};

type Result<T> = Success<T> | Failure;

export async function tryCatch<T>(
  promise: Promise<T>,
  options?: Options<T>,
): Promise<Result<T>> {
  try {
    const data = await promise;
    options?.onSuccess?.(data);
    return { data, isError: false } as Success<T>;
  } catch (error) {
    if (options?.logError) {
      console.error(options.logError, error);
    }
    options?.onError?.(error as Error);
    return { data: null, isError: true } as Failure;
  }
}

interface LogAndRethrowOptions<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
  logMessage?: string;
}

export async function logAndRethrow<T>(
  promiseFn: () => Promise<T>,
  options?: LogAndRethrowOptions<T>,
): Promise<T> {
  try {
    const data = await promiseFn();
    options?.onSuccess?.(data);
    return data;
  } catch (error) {
    if (options?.logMessage) {
      console.error(options.logMessage, error);
    } else {
      console.error(error);
    }
    options?.onError?.(error as Error);
    throw new TRPCError({ code: "INTERNAL_SERVER_ERROR", cause: error });
  }
}
