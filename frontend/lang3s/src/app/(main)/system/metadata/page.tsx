import { getUser } from "@/features/auth/server/actions";
import { roleHasPermissions } from "@/features/auth/permissions";
import { redirect } from "next/navigation";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { PlusIcon } from "lucide-react";
import { MetadataTable } from "@/features/metadata/ui/components/MetadataTable";
import { MetadataDialog } from "@/features/metadata/ui/components/MetadataDialog";
import { caller } from "@/lib/trpc/server";

const Page = async () => {
  const user = await getUser();
  if (!roleHasPermissions(user.role, ["metadata:edit"])) {
    redirect("/");
  }
  const [metadata, possibleMetadata] = await Promise.all([
    caller.system.getMetadata(),
    caller.system.getPossibleMetadata(),
  ]);
  return (
    <>
      <ScrollableBox.Container>
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
        <ScrollableBox.ScrollArea outerClassName="p-0!">
          <MetadataTable metadata={metadata} />
        </ScrollableBox.ScrollArea>
      </ScrollableBox.Container>
      <MetadataDialog possibleMetadata={possibleMetadata} />
    </>
  );
};

export default Page;
