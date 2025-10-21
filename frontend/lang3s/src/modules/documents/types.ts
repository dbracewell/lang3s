import { TextAnnotationDB } from "@/modules/common/classes";

export type GetDocumentResult = {
   id: string;
   metadata: Record<string, string>;
   text?: {
      id: string;
      text: string;
      annotations: TextAnnotationDB[];
   };
};
