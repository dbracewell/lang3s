import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth/auth";

export async function GET(req: NextRequest) {
  const apiKey = req.headers.get("lang3s-api-key");
  if (!apiKey) {
    return NextResponse.json({ valid: false });
  }
  try {
    const data = await auth.api.verifyApiKey({
      headers: req.headers,
      body: {
        key: apiKey,
      },
    });
    if (data.error) {
      return NextResponse.json({ valid: false });
    }
    const session = await auth.api.getSession({
      headers: req.headers,
    });

    return NextResponse.json({
      valid: data.valid,
      user: session?.user.id,
      role: session?.user.role!,
    });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ valid: false });
  }
}
