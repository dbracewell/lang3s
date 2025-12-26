import { db } from "@/lib/db";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import verb_ontology from "./verb_ontology.json";

type Node = {
  id?: number;
  name: string;
  description: string;
  children: Node[];
  mappings: string[];
};

const create_node = async (node: Node, parent?: Node) => {
  try {
    console.log(parent ? `${parent.name}.${node.name}` : node.name);
    const [r] = await db
      .insert(OntologyTable)
      .values({
        name: node.name,
        description: node.description,
        path: parent ? `${parent.name}.${node.name}` : node.name,
        parentId: parent?.id ? parent.id : undefined,
      })
      .returning();
    node.id = r.id;
    node.name = r.path;
    if (node.mappings.length > 0) {
      await db
        .insert(AnnotationToOntology)
        .values(
          node.mappings.map((m) => ({ ontologyId: r.id, annotation: m })),
        );
    }

    for (const child of node.children ?? []) {
      await create_node(child, node);
    }
  } catch (error) {
    console.log(error);
    console.log(node);
  }
};

const ALL: Node = {
  name: "ALL",
  description: "Root of all entities and concepts in the ontology",
  children: [],
  mappings: [],
};

const process_node = (parent: Node, entry: Record<string, any>) => {
  const newNode = {
    name: entry.name,
    description: !!entry.description.trim() ? entry.description : "",
    children: [],
    mappings: !!entry.mappings ? entry.mappings : [],
  } as Node;
  parent.children.push(newNode);
  (entry.children ?? []).forEach((child: Record<string, any>) =>
    process_node(newNode, child),
  );
};

Object.entries(verb_ontology).forEach(([root, entry]) => {
  process_node(ALL, entry);
});

create_node(ALL);
