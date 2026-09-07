import {
  getCurrentUser,
  roleHasPermissions,
} from "@/features/auth/server/actions";
import { redirect } from "next/navigation";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { PlusIcon } from "lucide-react";
import { MetadataTable } from "@/features/metadata/ui/components/MetadataTable";
import { MetadataDialog } from "@/features/metadata/ui/components/MetadataDialog";

const Page = async () => {
  const user = await getCurrentUser();
  if (!(await roleHasPermissions(user.role, ["metadata:edit"]))) {
    redirect("/");
  }
  return (
    <>
      <ScrollableBox.Container className="m-1">
        <ScrollableBox.Header>
          <h1>Metadata Editor</h1>
          <p className="pageSubheading">
            Add, edit, and delete metadata associated with documents, sentences,
            and annotations
          </p>
        </ScrollableBox.Header>
        <Link
          href="?edit=true"
          className={buttonVariants({
            variant: "listButton",
            className: "mb-3 w-fit",
            size: "sm",
          })}
        >
          <PlusIcon /> Add Metadata
        </Link>
        <ScrollableBox.ScrollArea outerClassName="p-0! bg-card">
          <MetadataTable />
        </ScrollableBox.ScrollArea>
      </ScrollableBox.Container>
      <MetadataDialog />
    </>
  );
};

export default Page;
