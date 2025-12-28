import { getUser } from "@/features/auth/server/actions";
import { roleHasPermissions } from "@/features/auth/permissions";
import { redirect } from "next/navigation";
import { MetadataPageView } from "@/features/metadata/ui/views/MetadataPageView";

const Page = async () => {
  const user = await getUser();
  if (!roleHasPermissions(user.role, ["metadata:edit"])) {
    redirect("/");
  }
  return <MetadataPageView />;
};

export default Page;
