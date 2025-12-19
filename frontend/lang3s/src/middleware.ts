import { NextRequest, NextResponse } from "next/server";
import { headers } from "next/headers";
import { auth } from "@/lib/auth/auth";

const publicRoutes = ["sign-in", "install"];
const authRoutes = ["sign-in", "install"];

export async function middleware(request: NextRequest) {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  const page = request.url.split("/").pop() ?? "'";

  if (!session && !publicRoutes.includes(page)) {
    return NextResponse.redirect(new URL("/sign-in", request.url));
  } else if (session && authRoutes.includes(page)) {
    return NextResponse.redirect(new URL("/", request.url));
  } else if (session?.user.role !== "admin" && request.url.includes("/admin")) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  runtime: "nodejs",
  matcher: ["/((?!api|api/inngest|_next/static|_next/image|.*\\.png$).*)"],
};
