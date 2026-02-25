from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from sqlalchemy import String, func, select

from lang3s.data.db import db
from lang3s.data.db.models import AnnotationToOntologyTable, OntologyTable


def is_ontology_type(ont_type: str, target: str) -> bool:
    ont_type = ont_type.lower()
    target = target.lower()
    if ont_type.endswith(f".{target}"):
        return True
    if ont_type.startswith(f"{target}."):
        return True
    if f".{target}." in ont_type:
        return True
    return False


@dataclass
class OntologyProperty:
    value: str
    dataType: Literal["string", "boolean", "number", "metadata"]
    inherit: bool
    display: bool
    definedBy: Optional[str] = None


@dataclass
class OntologyEntry:
    id: int
    name: str
    parent_id: int | None
    path: str
    properties: dict[str, OntologyProperty]
    parent_node: OntologyEntry = None
    children: list[OntologyEntry] = field(default_factory=list)

    @property
    def depth(self):
        return len(self.path.split("."))

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    @property
    def ancestors(self) -> list[OntologyEntry]:
        ancestors = []
        to_process: list[OntologyEntry] = self.children.copy()
        while len(to_process) > 0:
            node = to_process.pop()
            ancestors.append(node)
            to_process.extend(node.children)
        return ancestors


class Ontology:
    def __init__(self):
        self.path2node: dict[str, OntologyEntry] = {}
        self.name2node: dict[str, OntologyEntry] = {}
        self.root: OntologyEntry = self._load_ontology()
        self.mappings: dict[str, str] = {}
        self._load_mappings()

    def _load_mappings(self) -> None:
        with db.get_session() as session:
            entry: AnnotationToOntologyTable
            for entry in session.execute(select(AnnotationToOntologyTable)).scalars():
                self.mappings[entry.annotation] = entry.ontology.path

    def _load_ontology(self) -> OntologyEntry:
        nodes = {}
        root = None

        with db.get_session() as session:
            # Fetch everything in one go
            query = select(OntologyTable).order_by(OntologyTable.path.asc())
            for entry in session.execute(query).scalars():
                new_entry = OntologyEntry(
                    id=entry.id,
                    name=entry.name,
                    parent_id=entry.parentId,
                    path=entry.path,
                    properties={
                        k: OntologyProperty(**v)
                        for k, v in entry.properties.items()
                        if isinstance(v, dict)
                    },
                )

                nodes[new_entry.id] = new_entry
                self.path2node[new_entry.path] = new_entry
                self.name2node[new_entry.name] = new_entry

                if entry.parentId is None:
                    root = new_entry
                else:
                    parent = nodes.get(entry.parentId)
                    if parent:
                        new_entry.parent_node = parent
                        parent.children.append(new_entry)

        self._propagate_metadata(root)
        return root

    def _propagate_metadata(self, root: OntologyEntry):
        if not root:
            return

        # Stack stores (node, inherited_dict)
        stack = [(root, {k: v for k, v in root.properties.items() if v.inherit})]

        while stack:
            current, inherited = stack.pop()

            for child in current.children:
                # Only create a new dict if there's actually something to merge
                child_inheritable = {
                    k: v for k, v in child.properties.items() if v.inherit
                }

                # Update child properties with parent's inherited traits
                # child.properties.update(inherited) is fast but watch for overwrite logic
                merged = {**inherited, **child_inheritable}
                child.properties.update(merged)

                stack.append((child, merged))

    def _get_node(self, ont_type: str) -> OntologyEntry:
        node = self.path2node.get(ont_type, self.name2node.get(ont_type, None))
        if node is None:
            raise KeyError(ont_type)
        return node

    def refresh(self):
        self.path2node.clear()
        self.name2node.clear()
        self.mappings.clear()
        self.root = self._load_ontology()
        self._load_mappings()

    def __getitem__(self, item) -> OntologyEntry:
        return self._get_node(item)

    @property
    def nodes(self) -> list[OntologyEntry]:
        return list(self.path2node.values())

    def get_ontology_concept_for_mapping(self, mapping: str) -> str | None:
        return self.mappings.get(mapping, None)

    def get_common_ancestor(self, type_a: str, type_b: str) -> str:
        """Finds the lowest common ancestor to determine compatibility."""
        path_a = self._get_node(type_a).path.split(".")
        path_b = self._get_node(type_b).path.split(".")

        # Traverse paths to find divergence point
        last_common = "ALL"
        for p_a, p_b in zip(path_a, path_b):
            if p_a == p_b:
                last_common = p_a
            else:
                break
        return last_common

    def is_compatible(self, type_a: str, type_b: str) -> bool:
        if type_a == type_b:
            return True
        node_a = self._get_node(type_a)
        node_b = self._get_node(type_b)

        if node_a.parent_id == node_b.parent_id:
            return True

        return node_b in node_a.ancestors or node_a in node_b.ancestors

    def compatibility_score(self, type_a: str, type_b: str) -> float:
        """
        Returns 1.0 for perfect match, 0.5 for sibling match,
        0.0 for distinct top-level branches (e.g. Person vs Org).
        """
        if type_a == type_b:
            return 1.0

        ancestor = self.get_common_ancestor(type_a, type_b)
        ancestor_depth = len(ancestor.split("."))

        # Hard constraint: If ancestor is the root 'Entity', they are likely distinct
        # (e.g. Person vs Org).
        if ancestor == "ALL":
            return 0.0

        distance = min(
            len(type_a.split(".")) - ancestor_depth,
            len(type_b.split(".")) - ancestor_depth,
        )

        # Soft constraint: They share a branch (e.g. Politician vs Artist)
        return 1 / distance


ontology: Ontology = Ontology()
