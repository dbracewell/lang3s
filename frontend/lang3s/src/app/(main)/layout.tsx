import UserProvider from "@/features/auth/contexts/UserContext";
import { Wrapper } from "@/components/main-layout/Wrapper";
import "../globals.css";
import { getUserAndNavigation } from "@/features/auth/server/actions";

const MainLayout = async (props: LayoutProps<"/">) => {
  const r = await getUserAndNavigation();
  return (
    <UserProvider
      user={{
        username: r.user.username,
        name: r.user.name,
        email: r.user.email,
        id: r.user.id,
        role: r.user.role,
      }}
      navigation={r.navigation}
    >
      <Wrapper>{props.children}</Wrapper>
    </UserProvider>
  );
};

export default MainLayout;
