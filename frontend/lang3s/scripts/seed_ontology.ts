import { db } from "@/db";
import { OntologyTable } from "@/db/schemas/ontology";
import verb_ontology from "./verb_ontology.json";

type Node = {
  id?: number;
  name: string;
  description: string;
  children: Node[];
  mappings: string[];
};

const create_node = async (node: Node, parent?: Node) => {
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

  for (const child of node.children ?? []) {
    await create_node(child, node);
  }
};

const paths: Node = {
  name: "ALL",
  description: "Root of all entities and concepts in the ontology",
  children: [],
  mappings: [],
};

Object.entries(verb_ontology).forEach(([root, entry]) => {
  paths.children = paths.children.map((child) => {
    if (child.name === root) {
      return {
        name: child.name,
        description: !!child.description.trim()
          ? child.description
          : entry.description,
        children: [...child.children, ...entry.children],
        mappings: [...new Set([...child.mappings, entry.mappings])],
      } as Node;
    }
    return child;
  });
});

create_node(paths);
