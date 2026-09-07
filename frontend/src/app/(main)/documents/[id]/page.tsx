"use client";
import React from "react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { XIcon } from "lucide-react";
import { DocumentView } from "@/features/documents/ui/components/DocumentView";
import { GoBackButton } from "@/components/buttons/GoBackButton";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { documentsGetOneOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import { Spinner } from "@/components/Spinner";
import { DocumentSchema } from "@/lib/nlp/schemas";

const DocumentIdPage = () => {
  const { id } = useParams();
  const { data, isPending, error } = useQuery({
    ...documentsGetOneOptions({
      client: coreClient,
      path: {
        document_id: id as string,
      },
    }),
    staleTime: 60 * 60 * 1000,
  });

  if (error) {
    throw error;
  }

  if (isPending || data == null) {
    return <Spinner />;
  }

  const documentData = DocumentSchema.parse(data);

  return (
    <div className="animate-zoomin flex h-full flex-1 overflow-hidden">
      <Card className="m-1 flex min-h-0 flex-1 flex-col">
        <CardHeader>
          <CardTitle>{documentData.title}</CardTitle>
          <CardDescription className="text-muted-foreground flex flex-wrap gap-2 text-xs">
            {Object.entries(documentData.metadata_json)
              .filter(([k, _]) => k !== "mime-type")
              .map(([k, v], i) => (
                <div key={k}>
                  {i > 0 && <>|&nbsp;&nbsp;</>}
                  <span className="font-medium">{k}</span> : {String(v)}
                </div>
              ))}
          </CardDescription>
          <CardAction className="flex items-center gap-10">
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
