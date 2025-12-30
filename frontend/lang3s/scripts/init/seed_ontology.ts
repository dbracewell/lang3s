import { db } from "@/lib/db";
import {
  AnnotationToOntology,
  OntologyProperties,
  OntologyTable,
} from "@/lib/db/schemas/ontology";
import verb_ontology from "./verb_ontology.json";
import entity_ontology from "./entity_ontology.json";
import { AnnotationColors } from "@/features/common/constants";

type Node = {
  id?: number;
  name: string;
  description: string;
  children: Node[];
  mappings: string[];
  properties?: OntologyProperties;
};

const COLORS = [...Object.keys(AnnotationColors)];

const getColorName = (name: string) => {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % COLORS.length;
  return COLORS[index];
};

const create_node = async (node: Node, parent?: Node) => {
  try {
    const [r] = await db
      .insert(OntologyTable)
      .values({
        name: node.name,
        description: node.description,
        color: getColorName(node.name),
        path: parent ? `${parent.name}.${node.name}` : node.name,
        parentId: parent?.id ? parent.id : undefined,
        properties: node.properties,
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

export const seed_ontology = async () => {
  const ALL: Node = {
    name: "ALL",
    description: "Root of all entities and concepts in the ontology",
    children: [],
    mappings: [],
  };

  const process_node = (parent: Node, entry: Record<string, any>) => {
    if (entry["description"] == null) {
      console.log(entry);
    }
    const newNode = {
      name: entry.name,
      description: !!entry.description.trim() ? entry.description : "",
      children: [],
      mappings: !!entry.mappings ? entry.mappings : [],
      properties: entry["properties"] ?? {},
    } as Node;
    parent.children.push(newNode);
    (entry.children ?? []).forEach((child: Record<string, any>) =>
      process_node(newNode, child),
    );
  };

  Object.entries(verb_ontology).forEach(([root, entry]) => {
    process_node(ALL, entry);
  });
  Object.entries(entity_ontology).forEach(([root, entry]) => {
    process_node(ALL, entry);
  });

  await create_node(ALL);
};
