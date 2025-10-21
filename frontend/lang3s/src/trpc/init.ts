import { auth } from "@/lib/auth";
import { isValidApiKey } from "@/modules/jobs/server/api";
import { initTRPC, TRPCError } from "@trpc/server";
import { headers } from "next/headers";
import { cache } from "react";
import superjson from "superjson";
import z from "zod";

export const createTRPCContext = cache(async () => {
  const headerList = await headers();
  const session = await auth.api.getSession({ headers: headerList });
  if (session == null) {
    return {
      user: undefined,
    };
  }
  if (session.user.banned) {
    return {
      user: undefined,
    };
  }
  return {
    user: {
      id: session.user.id,
      role: session.user.role,
      username: session.user.username,
    },
  };
});

type Context = Awaited<ReturnType<typeof createTRPCContext>>;

const t = initTRPC.context<Context>().create({
  transformer: superjson,
});

const authenticated = t.middleware(async ({ next, ctx }) => {
  const { user } = ctx;

  if (!user?.id) {
    throw new TRPCError({ code: "UNAUTHORIZED" });
  }

  return next({
    ctx: {
      user: user,
    },
  });
});

// Base router and procedure helpers
export const createTRPCRouter = t.router;
export const createCallerFactory = t.createCallerFactory;
export const baseProcedure = t.procedure;
export const protectedProcedure = t.procedure.use(authenticated);

export const ApiEndpointSchema = z.object({
  api_key: z.string(),
});

export const apiMiddleWare = t.procedure
  .input(ApiEndpointSchema)
  .use(async (opts) => {
    opts.input.api_key;
    console.log(opts.input);
    if (!(await isValidApiKey(opts.input.api_key))) {
      throw new TRPCError({ code: "UNAUTHORIZED" });
    }
    return opts.next();
  });
