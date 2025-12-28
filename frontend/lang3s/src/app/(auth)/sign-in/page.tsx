import { SignInPageView } from "@/features/auth/ui/views/SignInPageView";
import { redirect } from "next/navigation";
import { getUserCount } from "@/features/auth/server/actions";

const SigninPage = async (props: PageProps<"/sign-in">) => {
  const searchParams = await props.searchParams;
  const userCount = await getUserCount();
  if (userCount <= 0) {
    redirect("/install");
  }
  return <SignInPageView redirect={searchParams["redirect"] as string} />;
};

export default SigninPage;
