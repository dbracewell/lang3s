CREATE TABLE IF NOT EXISTS text_annotations
(
    id           TEXT PRIMARY KEY,
    text         TEXT,
    surface      TEXT,
    type         TEXT,
    mapping      TEXT,
    value        TEXT,
    sentence_aid TEXT,
    document_id  TEXT,
    embedding    FLOAT[384],
    metadata     JSON
);


CREATE VIEW IF NOT EXISTS text_annotations_mapped
AS (
 select a.*, o.name as name, o.path as path, CONCAT(a.text,'-',o.path)as normalized_path
   from text_annotations a
   inner join pg_db.public.annotation_to_ontology ato on a.mapping = ato.annotation_type_value
   inner join pg_db.public.ontology o on ato.ontology_id = o.id
 );

CREATE VIEW IF NOT EXISTS text_annotations_mapped_counts AS
WITH ta_mapped AS (
    select a.*, o.name as name, o.path as path, CONCAT(a.text,'-',o.path)as normalized_path
   from text_annotations a
   inner join pg_db.public.annotation_to_ontology ato on a.mapping = ato.annotation_type_value
   inner join pg_db.public.ontology o on ato.ontology_id = o.id
)
select a.*,
       count(*) OVER (PARTITION BY text, path) as mention_count,
    count(distinct sentence_aid) OVER (PARTITION BY text, path) as sentence_count,
    count(distinct document_id) OVER (PARTITION BY text, path) as document_count,
    (count(*) OVER (PARTITION BY text, path)::FLOAT /
     NULLIF(count(distinct document_id) OVER (PARTITION BY text, path), 0)
    ) as mentions_per_document
from ta_mapped a