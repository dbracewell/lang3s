"use client";
import { AnnotationTypeValueFormDialog } from "@/components/dialogs/AnnotationTypeValueFormDialog";
import { ColorPickerDialog } from "@/components/dialogs/ColorPickerDialog";
import { LoadingButton } from "@/components/ui/loading-button";
import { AnnotationColors, ONTOLOGY_ROOT } from "@/features/common/constants";
import { AddPropertyDialog } from "@/features/ontology/ui/components/AddPropertyDialog";
import { useOntology } from "@/features/ontology/ui/components/OntologySelector";
import { cn } from "@/lib/utils/cn";
import { ArrowUpFromLine, RouteIcon, TablePropertiesIcon } from "lucide-react";
import { parseAsString, useQueryState } from "nuqs";
import { useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateOntologyEntryMutation } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { toast } from "sonner";
import { BasicUserInfo } from "@/features/common/types";
import { updateAnalytics } from "@/features/analytics/server/actions";
import { useUser } from "@/features/auth/contexts/UserContext";
import { z } from "zod";
import { zOntologyProperty } from "@/clients/core/zod.gen";

export const OntologyEditorInformationPanel = () => {
  const { currentNode, rootNode } = useOntology();
  const queryClient = useQueryClient();
  const updateOntology = useMutation({
    ...updateOntologyEntryMutation({
      client: coreClient,
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      toast.success("Successfully updated ontology");
    },
    onError: () => toast.error("Failed to update ontology"),
  });

  const [, setPathParam] = useQueryState(
    "path",
    parseAsString
      .withDefault(rootNode)
      .withOptions({ clearOnDefault: true, shallow: true }),
  );

  useEffect(() => {
    setPathParam(currentNode ? currentNode.path : "");
  }, [currentNode, setPathParam]);

  if (currentNode == null) {
    return null;
  }

  return (
    <div className="flex flex-1 flex-col gap-3 pt-3">
      <div className="flex flex-col gap-1 border-b pb-2">
        <div className="mb-2 flex flex-col gap-1">
          <PublishChangesButton />
          <span className="text-muted-foreground px-2 text-xs">
            * Perform if the mappings are modified or concepts are moved or
            renamed. <br />
            (This operation can take some time. You may close the page.)
          </span>
        </div>
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
          <ColorPickerDialog
            title={
              <div>
                Visualization color for{" "}
                <span className="text-dodger-blue-500 font-bold">
                  {currentNode.name}
                </span>
              </div>
            }
            defaultColor={currentNode.color}
            onSelect={(color) =>
              updateOntology.mutate({
                body: {
                  id: currentNode.id!,
                  color,
                },
              })
            }
          />
        </div>
      </div>
      <div
        className={cn(
          "flex flex-col gap-1 border-b pb-2",
          Object.keys(currentNode.properties ?? {}).length > 0 && "pb-5!",
        )}
      >
        <div className="flex items-center justify-between gap-2 pb-2">
          <h4 className="truncate text-xs font-medium">Properties</h4>
          {currentNode.path !== ONTOLOGY_ROOT && (
            <AddPropertyDialog
              title={
                <>
                  Properties for{" "}
                  <span className="text-dodger-blue-500 font-bold">
                    {currentNode.name}
                  </span>
                </>
              }
              defaultValues={
                currentNode.properties as unknown as z.infer<
                  typeof zOntologyProperty
                >[]
              }
              onSelect={(properties) => {
                updateOntology.mutate({
                  body: {
                    id: currentNode.id!,
                    properties,
                  },
                });
              }}
            />
          )}
        </div>
        {Object.keys(currentNode.properties ?? {}).length > 0 ? (
          <table className="border text-sm">
            <thead>
              <tr className="bg-heading text-white">
                <th className="p-1">Property</th>
                <th className="p-1">Value</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(currentNode.properties ?? {}).map(([k, v]) => (
                <tr className="bg-row odd:bg-alternate-row" key={k}>
                  <td className="p-1">{k}</td>
                  <td className="p-1">
                    {String(v.value)} {v.definedBy && <>({v.definedBy})</>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex h-25 w-full flex-col items-center justify-center gap-2">
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
          {currentNode.path !== ONTOLOGY_ROOT && (
            <AnnotationTypeValueFormDialog
              title={
                <div>
                  Annotation Mappings for{" "}
                  <span className="text-dodger-blue-500 font-bold">
                    {currentNode.name}
                  </span>
                </div>
              }
              defaultValues={currentNode.mappings?.map((m) => m.mapping) ?? []}
              onSelectAction={(mapping) => {
                updateOntology.mutate({
                  body: {
                    id: currentNode.id!,
                    mapping,
                  },
                });
              }}
            />
          )}
        </div>
        {currentNode.mappings && currentNode.mappings.length > 0 ? (
          <table className="border text-sm">
            <thead>
              <tr className="bg-heading text-white">
                <th className="p-1">Annotation Type</th>
                <th className="p-1">Annotation Value</th>
              </tr>
            </thead>
            <tbody>
              {currentNode.mappings.map((m) => (
                <tr className="bg-row odd:bg-alternate-row" key={m.mapping}>
                  <td className="p-1">{m.mapping.split(":")[0]}</td>
                  <td className="p-1">{m.mapping.split(":")[1]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex h-25 w-full flex-col items-center justify-center gap-2">
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

const PublishChangesButton = () => {
  const updateTables = useMutation({
    mutationFn: async (user: BasicUserInfo) => updateAnalytics(user),
    onError: () => {
      toast.error("Failed to publish changes and update analytics");
    },
  });
  const user = useUser();
  return (
    <LoadingButton
      isLoading={updateTables.isPending}
      disabled={updateTables.isPending}
      type="button"
      variant="ghost"
      size="sm"
      onClick={() => updateTables.mutate(user)}
    >
      <div className="flex items-center gap-2">
        <ArrowUpFromLine /> Publish changes to analytics
      </div>
    </LoadingButton>
  );
};
