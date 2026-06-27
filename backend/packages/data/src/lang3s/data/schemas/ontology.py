from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from lang3s.core.collections_extras import hashed_select
from lang3s.core.constants import COLOR_NAMES


class OntologyMapping(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Annotated[int | None, WithJsonSchema({"type": "integer", "nullable": True})] = (
        None
    )
    mapping: str


class OntologyProperty(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    value: str | bool | int | float | list[str]
    dataType: Literal["string", "boolean", "number", "metadata"]
    inherit: bool = False
    display: bool = False
    definedBy: Annotated[
        str | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None


class IsolatedOntologyEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Annotated[int | None, WithJsonSchema({"type": "integer", "nullable": True})] = (
        None
    )
    name: str
    path: str
    description: str
    color: str
    parent_id: Annotated[
        int | None, WithJsonSchema({"type": "integer", "nullable": True})
    ] = None
    mappings: list[OntologyMapping] = Field(default_factory=list)
    properties: dict[str, OntologyProperty] = Field(default_factory=dict)

    @field_validator("path", mode="before")
    @classmethod
    def stringify_ltree(cls, v: Any) -> str:
        """
        Converts the Ltree object to a standard string.
        """
        if v is not None:
            return str(v)
        return ""

    @field_validator("properties", mode="before")
    @classmethod
    def convert_properties(cls, v: Any) -> dict[str, OntologyProperty]:
        """
        Converts the Ltree object to a standard string.
        """
        if v is not None:
            properties: dict[str, OntologyProperty] = {}
            for key, value in v.items():
                properties[key] = OntologyProperty(**value)
            return properties
        return {}


class OntologyEntry(IsolatedOntologyEntry):
    model_config = ConfigDict(from_attributes=True)
    parent_node: Optional[OntologyEntry] = Field(default=None, exclude=True)
    children: list[OntologyEntry] = Field(default_factory=list)

    def __str__(self):
        return f"OntologyEntry(path='{self.path}', n_children={len(self.children)})"

    @model_validator(mode="after")
    def wire_up_children(self) -> OntologyEntry:
        for child in self.children:
            child.parent_node = self
        return self

    def add_mapping(self, mapping: str) -> None:
        for m in self.mappings:
            if m.mapping == mapping:
                return
        self.mappings.append(OntologyMapping(mapping=mapping))

    @staticmethod
    def root() -> OntologyEntry:
        return OntologyEntry(
            name="ROOT",
            path="ROOT",
            color="RED",
            description="ROOT",
        )

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


class Ontology(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    root: OntologyEntry = Field(default_factory=lambda: OntologyEntry.root())
    mappings: dict[str, str] = Field(default_factory=dict)
    path_to_node: Dict[str, OntologyEntry] = Field(default_factory=dict, exclude=True)
    name_to_node: Dict[str, OntologyEntry] = Field(default_factory=dict, exclude=True)

    @model_validator(mode="after")
    def wire_node_mappings(self) -> Ontology:
        stack = [
            (
                self.root,
                {k: v for k, v in self.root.properties.items() if v.inherit},
            )
        ]
        while stack:
            current, inherited = stack.pop()
            self.path_to_node[current.path] = current
            self.name_to_node[current.name] = current
            for m in current.mappings:
                self.mappings[m.mapping] = current.path

            for child in current.children:
                child_inheritable = {
                    k: v for k, v in child.properties.items() if v.inherit
                }
                merged = {**inherited, **child_inheritable}
                child.properties.update(merged)
                merged = {
                    **inherited,
                    **{
                        k: OntologyProperty(
                            **v.model_dump(exclude_none=True, exclude={"definedBy"}),
                            definedBy=child.path,
                        )
                        for k, v in child_inheritable.items()
                    },
                }
                stack.append((child, merged))

        return self

    def _get_node(self, ont_type: str) -> OntologyEntry:
        node = self.path_to_node.get(ont_type, self.name_to_node.get(ont_type, None))
        if node is None:
            raise KeyError(ont_type)
        return node

    def __getitem__(self, item) -> OntologyEntry:
        return self._get_node(item)

    def __contains__(self, item) -> bool:
        return item in self.path_to_node or item in self.name_to_node

    def add_node(
        self,
        name: str,
        description: str,
        parent: OntologyEntry | str,
    ) -> OntologyEntry:
        if name in self.name_to_node:
            raise KeyError(name)

        if isinstance(parent, str):
            parent_node = self._get_node(parent)
            if parent is None:
                raise KeyError(parent)
        else:
            parent_node = parent

        child = OntologyEntry(
            name=name,
            path=f"{parent.path}.{name}",
            description=description,
            color=hashed_select(name, COLOR_NAMES),
            parent_id=parent_node.id,
            parent_node=parent_node,
        )
        parent_node.children.append(child)
        self.name_to_node[name] = child
        self.path_to_node[child.path] = child
        return child

    def set_property(
        self,
        entry: OntologyEntry | str,
        property_name: str,
        property_value: OntologyProperty,
    ):
        if isinstance(entry, str):
            entry_node = self._get_node(entry)
            if entry_node is None:
                raise KeyError(entry)
        else:
            entry_node = entry
        entry_node.properties[property_name] = property_value
        if property_value.inherit:
            new_property = property_value.model_copy()
            new_property.definedBy = entry_node.path
            stack = entry_node.children
            while stack:
                current = stack.pop()
                stack.extend(current.children)
                if property_name not in current.properties:
                    current.properties[property_name] = new_property

    @property
    def nodes(self) -> list[OntologyEntry]:
        return list(self.path_to_node.values())

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

    @staticmethod
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


class AnnotationIdOntologyMapping(BaseModel):
    annotation_id: str
    name: str
    path: str
    color: str


class AnnotationOntologyMappingList(BaseModel):
    mapping: dict[str, AnnotationIdOntologyMapping]


class OntologyFrontEnd(BaseModel):
    paths: list[str]
    nodes: dict[str, IsolatedOntologyEntry]


class OntologyUpdateRequest(BaseModel):
    id: int
    color: str | None = None
    description: str | None = None
    properties: dict[str, OntologyProperty] | None = None
    mapping: list[str] | None = None


class OntologyEntryCreationRequest(BaseModel):
    parent_id: int
    name: str
    description: Annotated[
        str | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None


class OntologyNameExists(BaseModel):
    exists: bool


class OntologyPaths(RootModel[List[str]]):
    pass


class PotentialMappingList(BaseModel):
    items: dict[str, str | None]
