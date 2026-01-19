import { Fragment } from "react";
import { DeleteMetadataButton } from "@/features/metadata/ui/components/DeleteMetadataButton";
import Link from "next/link";
import { formatURL } from "@/lib/utils/formatters";
import { buttonVariants } from "@/components/ui/button";
import { PencilIcon } from "lucide-react";
import { MetadataConfiguration, MetadataItem } from "@/features/metadata/types";

export const MetadataTable = ({
  metadata,
}: {
  metadata: MetadataConfiguration;
}) => {
  return (
    <table>
      <thead>
        <tr className="bg-heading text-white">
          <th className="p-1 pl-4 text-left">Source</th>
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
              <Row
                key={`${source}-${name}`}
                source={source}
                name={name}
                data={data}
              />
            ))}
          </Fragment>
        ))}
      </tbody>
    </table>
  );
};

const Row = ({
  source,
  name,
  data,
}: {
  source: string;
  name: string;
  data: MetadataItem;
}) => {
  return (
    <tr key={`${source}-${name}`} className="bg-row odd:bg-alternate-row">
      <td className="p-1 pl-4">{source}</td>
      <td className="p-1">{name}</td>
      <td className="p-1">{data.dataType}</td>
      <td className="p-1">{data.formatter}</td>
      <td className="w-10 p-1 pr-4">
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
  );
};
