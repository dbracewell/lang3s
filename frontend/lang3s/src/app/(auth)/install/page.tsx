import { getUserCount } from "@/modules/auth/server/actions";
import { InstallPageView } from "@/modules/auth/ui/views/InstallPageView";
import { redirect } from "next/navigation";

const InstallPage = async () => {
  const userCount = await getUserCount();
  if (userCount > 0) {
    redirect("/sign-in");
  }
  return <InstallPageView />;
};

export default InstallPage;
