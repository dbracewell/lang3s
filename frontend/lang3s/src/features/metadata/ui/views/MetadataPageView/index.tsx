import { caller } from "@/lib/trpc/server";
import { MetadataDialog } from "@/features/metadata/ui/views/MetadataPageView/MetadataDialog";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { PencilIcon, PlusIcon } from "lucide-react";
import { Fragment } from "react";
import { formatURL } from "@/lib/utils/formatters";
import { DeleteMetadataButton } from "@/features/metadata/ui/views/MetadataPageView/DeleteMetadataButton";

export const MetadataPageView = async () => {
  const [metadata, possibleMetadata] = await Promise.all([
    caller.system.getMetadata(),
    caller.system.getPossibleMetadata(),
  ]);
  return (
    <>
      <MetadataDialog possibleMetadata={possibleMetadata} />
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
          <table>
            <thead>
              <tr className="bg-heading text-white">
                <th className="p-1 text-left">Source</th>
                <th className="p-1 text-left">Name</th>
                <th className="p-1 text-left">Data Type</th>
                <th className="p-1 text-left">Formatter</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metadata).map(([source, items]) => (
                <Fragment key={source}>
                  {Object.entries(items).map(([name, data]) => (
                    <tr
                      key={`${source}-${name}`}
                      className="bg-row odd:bg-alternate-row"
                    >
                      <td className="p-2">{source}</td>
                      <td className="p-2">{name}</td>
                      <td className="p-2">{data.dataType}</td>
                      <td className="p-2">{data.formatter}</td>
                      <td className="w-[40px] p-2">
                        <div className="flex items-center gap-2">
                          <DeleteMetadataButton name={name} id={data.id} />
                          <Link
                            href={formatURL("/system/metadata", {
                              edit: true,
                              id: data.id,
                              source,
                              name,
                              dataType: data.dataType,
                              formatter: data.formatter,
                            })}
                            className={buttonVariants({
                              variant: "ghost",
                              size: "sm",
                            })}
                          >
                            <PencilIcon />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </ScrollableBox.ScrollArea>
      </ScrollableBox.Container>
    </>
  );
};
