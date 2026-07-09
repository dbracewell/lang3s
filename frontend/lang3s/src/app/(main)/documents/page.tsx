import React from "react";
import { DocumentsViewPage } from "@/features/documents/ui/views/DocumentsViewPage";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";

const DocumentsPage = () => {
  return (
    <ScrollableBox.Container className="m-1 gap-2">
      <ScrollableBox.Header>
        <h1>Documents</h1>
      </ScrollableBox.Header>
      <DocumentsViewPage />
    </ScrollableBox.Container>
  );
};

export default DocumentsPage;
