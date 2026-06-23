from lang3s.data.db import get_ontology
from lang3s.data.schemas import Ontology, TextAnnotation

NO_COREF_ONTOLOGY_TYPES = {
    "ALL",
    "ALL.Entity.Abstract.Temporal_And_Occurrence",
    "ALL.Entity.Abstract.Temporal_And_Occurrence.Date",
    "ALL.Entity.Abstract.Temporal_And_Occurrence.Time",
    "ALL.Entity.Abstract.Value_And_Quantification",
    "ALL.Entity.Abstract.Value_And_Quantification.Cardinal",
    "ALL.Entity.Abstract.Value_And_Quantification.Money",
    "ALL.Entity.Abstract.Value_And_Quantification.Ordinal",
    "ALL.Entity.Abstract.Value_And_Quantification.Quantity",
    "ALL.Entity.Abstract.Value_And_Quantification.Percent",
}


def should_perform_coref(mention: TextAnnotation):
    if mention.type_ != "entity":
        return False
    ontology_type = get_ontology().get_ontology_concept_for_mapping(mention.mapping)
    if ontology_type is None:
        return False
    if not Ontology.is_ontology_type(ontology_type, "Entity"):
        return False
    if ontology_type in NO_COREF_ONTOLOGY_TYPES:
        return False
    return True
