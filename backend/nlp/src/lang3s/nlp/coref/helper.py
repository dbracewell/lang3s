from lang3s.nlp.shared_types import TextAnnotation
from lang3s.ontology import ontology
from lang3s.ontology.core import is_ontology_type

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
    if mention.type != "entity":
        return False
    ontology_type = ontology.get_ontology_concept_for_mapping(mention.mapping)
    if ontology_type is None:
        return False
    if not is_ontology_type(ontology_type, "Entity"):
        return False
    if ontology_type in NO_COREF_ONTOLOGY_TYPES:
        return False
    return True
