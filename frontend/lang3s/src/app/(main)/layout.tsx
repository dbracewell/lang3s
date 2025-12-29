import UserProvider from "@/features/auth/contexts/UserContext";
import { Wrapper } from "@/components/main-layout/Wrapper";
import { auth } from "@/lib/auth/auth";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import "../globals.css";
import { UserRole } from "@/features/auth/permissions";

const MainLayout = async (props: LayoutProps<"/">) => {
  const session = await auth.api.getSession({
    headers: await headers(),
  });
  const user = session?.user;
  if (user == null) {
    return redirect("/sign-in");
  }
  return (
    <UserProvider
      user={{
        id: user.id,
        role: user.role as UserRole,
        username: user.username ?? user.email,
      }}
    >
      <Wrapper>{props.children}</Wrapper>
    </UserProvider>
  );
};

export default MainLayout;
