import UserProvider from "@/features/auth/UserContext";
import { NavSidebar } from "@/components/main-layout/NavSidebar";

const MainLayout = async (props: LayoutProps<"/">) => {
  // const cookieStore = await cookies();
  // const defaultOpen = cookieStore.get("sidebar_state")?.value === "true";
  return (
    <UserProvider>
      {/*<SidebarProvider defaultOpen={false} className="p-0!">*/}
      {/*  <AppSidebar />*/}
      {/*  <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-gradient-to-b from-slate-100 to-slate-200">*/}
      {/*    <AppHeader />*/}
      {/*    <main className="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col py-5">*/}
      {/*      <div className="max-h-full min-h-0 flex-1 overflow-y-auto px-5">*/}
      {/*        {props.children}*/}
      {/*      </div>*/}
      {/*    </main>*/}
      {/*  </div>*/}
      {/*</SidebarProvider>*/}
      <NavSidebar isOpen={false} setIsOpen={() => {}} />
      {props.children}
    </UserProvider>
  );
};

export default MainLayout;
