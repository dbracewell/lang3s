import UserProvider from "@/features/auth/UserContext";
import { Wrapper } from "@/components/main-layout/Wrapper";

const MainLayout = async (props: LayoutProps<"/">) => {
  return (
    <UserProvider>
      <Wrapper>{props.children}</Wrapper>
    </UserProvider>
  );
};

export default MainLayout;
