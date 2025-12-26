import UserProvider from "@/features/auth/UserContext";
import { Wrapper } from "@/components/main-layout/Wrapper";
import { auth } from "@/lib/auth/auth";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { BasicUserInfo } from "@/features/common/types";
import "../globals.css";

const MainLayout = async (props: LayoutProps<"/">) => {
  const session = await auth.api.getSession({
    headers: await headers(),
  });
  const user = session?.user;
  if (user == null) {
    redirect("/sign-in");
  }
  return (
    <UserProvider user={user as BasicUserInfo}>
      <Wrapper>{props.children}</Wrapper>
    </UserProvider>
  );
};

export default MainLayout;
