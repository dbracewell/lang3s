import React from "react";
import {
  PagePermissions,
  roleHasPermissions,
} from "@/features/auth/permissions";
import { redirect } from "next/navigation";
import { getUser } from "@/features/auth/server/actions";
import { OntologyEditorPageView } from "@/features/ontology/ui/views/OntologyEditorPageView";

const OntologyEditorPage = async (
  props: PageProps<"/system/ontology/editor">,
) => {
  const user = await getUser();
  const searchParams = await props.searchParams;
  const selectedNode = searchParams["path"] as string;
  if (
    !roleHasPermissions(user.role, PagePermissions['"/system/ontology/editor"'])
  ) {
    redirect(
      `/system/ontology/viewer${selectedNode ? `?path=${selectedNode}` : ""}`,
    );
  }
  return <OntologyEditorPageView selectedNode={selectedNode} />;
};

export default OntologyEditorPage;
