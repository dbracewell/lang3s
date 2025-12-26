import React from "react";
import {
  PagePermissions,
  roleHasPermissions,
} from "@/features/auth/permissions";
import { redirect } from "next/navigation";
import { getUser } from "@/features/auth/server/actions";
import { OntologyEditorPageView } from "@/features/ontology/ui/views/OntologyEditorPageView";

const OntologyEditorPage = async () => {
  const user = await getUser();
  if (
    !roleHasPermissions(user.role, PagePermissions['"/system/ontology/editor"'])
  ) {
    redirect("/system/ontology/viewer");
  }
  return <OntologyEditorPageView />;
};

export default OntologyEditorPage;
