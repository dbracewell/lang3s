import React from "react";
import { redirect } from "next/navigation";
import { getUser, roleHasPermissions } from "@/features/auth/server/actions";
import { OntologyEditor } from "@/features/ontology/ui/components/OntologyEditor";
import { ScrollableBox } from "@/components/scrolling/Scrollbox";

const OntologyEditorPage = async (
  props: PageProps<"/system/ontology/editor">,
) => {
  const user = await getUser();
  const searchParams = await props.searchParams;
  const selectedNode = searchParams["path"] as string;
  if (!(await roleHasPermissions(user.role, ["ontology:edit"]))) {
    redirect(
      `/system/ontology/viewer${selectedNode ? `?path=${selectedNode}` : ""}`,
    );
  }
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Ontology Editor</h1>
        <p className="pageSubheading">Edit the system Ontology</p>
      </ScrollableBox.Header>
      <OntologyEditor selectedNode={selectedNode} />
    </ScrollableBox.Container>
  );
};

export default OntologyEditorPage;
