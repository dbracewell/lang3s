import { TextAnnotationProps } from "@/features/common/classes";

export type GetDocumentResult = {
  id: string;
  title: string;
  metadata: Record<string, string>;
  text: {
    id: string;
    text: string;
    annotations: TextAnnotationProps[];
  };
};
