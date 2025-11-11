import { DocumentView } from "@/components/text/DocumentView";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { GetDocumentResult } from "@/modules/documents/types";
import { NotebookTextIcon, XIcon } from "lucide-react";
import Link from "next/link";
import React from "react";

export const DocumentIdView = ({
  documentData,
}: {
  documentData: GetDocumentResult;
}) => {
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
            <Link
              href="/documents"
              className="hover:bg-accent/50 flex size-8 items-center justify-center rounded-md hover:border"
            >
              <XIcon />
            </Link>
          </CardAction>
        </CardHeader>
        <CardContent className="flex h-full min-h-0 flex-1">
          <DocumentView
            documentData={documentData}
            targetAnnotationType="entity"
          />
        </CardContent>
      </Card>
    </div>
  );
};
