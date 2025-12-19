import { db } from "@/lib/db";
import { user } from "@/lib/db/schema";
import { SignInPageView } from "@/features/auth/ui/views/SignInPageView";
import { redirect } from "next/navigation";

const getUserCount = async () => {
  return await db.$count(user);
};

const SigninPage = async () => {
  const userCount = await getUserCount();
  if (userCount <= 0) {
    redirect("/install");
  }
  return <SignInPageView />;
};

export default SigninPage;
