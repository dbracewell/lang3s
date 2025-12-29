import { caller } from "@/lib/trpc/server";
import React from "react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { NotebookTextIcon, XIcon } from "lucide-react";
import { DocumentView } from "@/features/documents/ui/components/DocumentView";
import { GoBackButton } from "@/components/buttons/GoBackButton";

const DocumentIdPage = async (props: PageProps<"/documents/[id]">) => {
  const { id } = await props.params;
  const documentData = await caller.documents.getOne({ id });

  return (
    <div className="flex h-full flex-1 overflow-hidden">
      <Card className="flex min-h-0 flex-1 flex-col">
        <CardHeader>
          <CardTitle>{documentData.title}</CardTitle>
          <CardDescription className="text-muted-foreground flex flex-wrap gap-2 text-xs">
            {Object.entries(documentData.metadata)
              .filter(([k, _]) => k !== "mime-type")
              .map(([k, v], i) => (
                <div key={k}>
                  {i > 0 && <>|&nbsp;&nbsp;</>}
                  <span className="font-medium">{k}</span> : {v}
                </div>
              ))}
          </CardDescription>
          <CardAction className="flex items-center gap-10">
            <Button variant="note">
              <NotebookTextIcon />
            </Button>
            <GoBackButton variant="ghost">
              <XIcon />
            </GoBackButton>
          </CardAction>
        </CardHeader>
        <CardContent className="flex h-full min-h-0 flex-1">
          <DocumentView documentData={documentData} />
        </CardContent>
      </Card>
    </div>
  );
};

export default DocumentIdPage;
