import { useOntology } from "@/components/ontology/OntologySelector";
import { AnnotationColors } from "@/features/common/constants";
import { cn } from "@/lib/utils/cn";
import { RouteIcon, TablePropertiesIcon } from "lucide-react";
import React from "react";

export const ExtraInformation = () => {
  const { currentNode } = useOntology();
  if (currentNode == null) {
    return null;
  }

  return (
    <div className="flex flex-1 flex-col gap-3 pt-3">
      <div className="flex flex-col gap-1 border-b pb-2">
        <h4 className="truncate text-xs font-medium">Visualization Color</h4>
        <div className="flex items-center justify-between gap-2 pb-2">
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "size-4 border",
                AnnotationColors[currentNode.color],
              )}
            />
            <div>{currentNode.color}</div>
          </div>
        </div>
      </div>
      <div
        className={cn(
          "flex flex-col gap-1 border-b pb-2",
          Object.keys(currentNode.properties).length > 0 && "pb-5!",
        )}
      >
        <div className="flex items-center justify-between gap-2 pb-2">
          <h4 className="truncate text-xs font-medium">Properties</h4>
        </div>
        {Object.keys(currentNode.properties).length > 0 ? (
          <table className="border text-sm">
            <thead>
              <tr className="bg-heading text-white">
                <th className="p-1">Property</th>
                <th className="p-1">Value</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(currentNode.properties).map(([k, v]) => (
                <tr className="bg-row odd:bg-alternate-row" key={k}>
                  <td className="p-1">{k}</td>
                  <td className="p-1">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex h-[100px] w-full flex-col items-center justify-center gap-2">
            <TablePropertiesIcon className="text-muted-foreground" />
            <h4 className="text-muted-foreground truncate font-medium">
              No Properties
            </h4>
          </div>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2 pb-2">
          <h4 className="truncate text-xs font-medium">Annotation Mappings</h4>
        </div>
        {currentNode.mappings.length > 0 ? (
          <table className="border text-sm">
            <thead>
              <tr className="bg-heading text-white">
                <th className="p-1">Annotation Type</th>
                <th className="p-1">Annotation Value</th>
              </tr>
            </thead>
            <tbody>
              {currentNode.mappings.map((m) => (
                <tr className="bg-row odd:bg-alternate-row" key={m}>
                  <td className="p-1">{m.split(":")[0]}</td>
                  <td className="p-1">{m.split(":")[1]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex h-[100px] w-full flex-col items-center justify-center gap-2">
            <RouteIcon className="text-muted-foreground" />
            <h4 className="text-muted-foreground truncate font-medium">
              No Mappings
            </h4>
          </div>
        )}
      </div>
    </div>
  );
};
