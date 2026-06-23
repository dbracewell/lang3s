-- Custom SQL migration file, put your code below! --
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;
CREATE EXTENSION IF NOT EXISTS ltree;

CREATE OR REPLACE FUNCTION jsonb_array_to_text_array(_js jsonb)
    RETURNS text[]
    LANGUAGE sql
    IMMUTABLE PARALLEL SAFE AS
$$
SELECT ARRAY(SELECT jsonb_array_elements_text(_js));
$$;

CREATE OR REPLACE FUNCTION lower_array(text[]) RETURNS text[]
    LANGUAGE sql
    IMMUTABLE AS
$$
SELECT array_agg(lower(x))
FROM unnest($1) x;
$$;



DROP TYPE IF EXISTS "public"."job_status" CASCADE;
DROP TYPE IF EXISTS "public"."job_type" CASCADE;
DROP TYPE IF EXISTS "public"."metadata_data_type" CASCADE;
DROP TYPE IF EXISTS "public"."metadata_sources" CASCADE;
CREATE TYPE "public"."job_status" AS ENUM ('waiting', 'processing', 'complete', 'failed');
CREATE TYPE "public"."job_type" AS ENUM ('annotation', 'update', 'other');
CREATE TYPE "public"."metadata_data_type" AS ENUM ('string', 'string[]', 'int', 'float', 'boolean', 'date', 'datetime');
CREATE TYPE "public"."metadata_sources" AS ENUM ('document', 'annotation', 'sentence');
CREATE TABLE IF NOT EXISTS "account"
(
    "id"                       text PRIMARY KEY        NOT NULL,
    "account_id"               text                    NOT NULL,
    "provider_id"              text                    NOT NULL,
    "user_id"                  text                    NOT NULL,
    "access_token"             text,
    "refresh_token"            text,
    "id_token"                 text,
    "access_token_expires_at"  timestamp,
    "refresh_token_expires_at" timestamp,
    "scope"                    text,
    "password"                 text,
    "created_at"               timestamp DEFAULT now() NOT NULL,
    "updated_at"               timestamp               NOT NULL
);

CREATE TABLE IF NOT EXISTS "apikey"
(
    "id"                     text PRIMARY KEY NOT NULL,
    "name"                   text,
    "start"                  text,
    "prefix"                 text,
    "key"                    text             NOT NULL,
    "user_id"                text             NOT NULL,
    "refill_interval"        integer,
    "refill_amount"          integer,
    "last_refill_at"         timestamp,
    "enabled"                boolean DEFAULT true,
    "rate_limit_enabled"     boolean DEFAULT true,
    "rate_limit_time_window" integer DEFAULT 86400000,
    "rate_limit_max"         integer DEFAULT 10,
    "request_count"          integer DEFAULT 0,
    "remaining"              integer,
    "last_request"           timestamp,
    "expires_at"             timestamp,
    "created_at"             timestamp        NOT NULL,
    "updated_at"             timestamp        NOT NULL,
    "permissions"            text,
    "metadata"               text
);

CREATE TABLE IF NOT EXISTS "session"
(
    "id"              text PRIMARY KEY        NOT NULL,
    "expires_at"      timestamp               NOT NULL,
    "token"           text                    NOT NULL,
    "created_at"      timestamp DEFAULT now() NOT NULL,
    "updated_at"      timestamp               NOT NULL,
    "ip_address"      text,
    "user_agent"      text,
    "user_id"         text                    NOT NULL,
    "impersonated_by" text,
    CONSTRAINT "session_token_unique" UNIQUE ("token")
);

CREATE TABLE IF NOT EXISTS "user"
(
    "id"               text PRIMARY KEY        NOT NULL,
    "name"             text                    NOT NULL,
    "email"            text                    NOT NULL,
    "email_verified"   boolean   DEFAULT false NOT NULL,
    "image"            text,
    "created_at"       timestamp DEFAULT now() NOT NULL,
    "updated_at"       timestamp DEFAULT now() NOT NULL,
    "role"             text,
    "banned"           boolean   DEFAULT false,
    "ban_reason"       text,
    "ban_expires"      timestamp,
    "username"         text,
    "display_username" text,
    CONSTRAINT "user_email_unique" UNIQUE ("email"),
    CONSTRAINT "user_username_unique" UNIQUE ("username")
);

CREATE TABLE IF NOT EXISTS "verification"
(
    "id"         text PRIMARY KEY        NOT NULL,
    "identifier" text                    NOT NULL,
    "value"      text                    NOT NULL,
    "expires_at" timestamp               NOT NULL,
    "created_at" timestamp DEFAULT now() NOT NULL,
    "updated_at" timestamp DEFAULT now() NOT NULL
);

DROP TABLE IF EXISTS "documents" CASCADE;
CREATE TABLE "documents"
(
    "id"         text PRIMARY KEY              NOT NULL,
    "title"      text                          NOT NULL,
    "metadata"   jsonb     DEFAULT '{}'::jsonb NOT NULL,
    "created_at" timestamp DEFAULT now(),
    "updated_at" timestamp DEFAULT now()
);

DROP TABLE IF EXISTS "text_annotations" CASCADE;
CREATE TABLE "text_annotations"
(
    "id"              text PRIMARY KEY              NOT NULL,
    "text"            text                          NOT NULL,
    "clean_text"      text                          NOT NULL,
    "normalized_text" text                          NOT NULL,
    "text_id"         text                          NOT NULL,
    "doc_id"          text                          NOT NULL,
    "start"           integer                       NOT NULL,
    "end"             integer                       NOT NULL,
    "sentence_id"     integer                       NOT NULL,
    "sentence_aid"    text                          NOT NULL,
    "type"            text                          NOT NULL,
    "value"           text                          NOT NULL,
    "source"          text                          NOT NULL,
    "mapping"         text,
    "embedding"       halfvec(384)                  NOT NULL,
    "metadata"        jsonb     DEFAULT '{}'::jsonb NOT NULL,
    "a0_text"         text[] GENERATED ALWAYS AS (jsonb_array_to_text_array(metadata -> 'A0_TEXT')) STORED,
    "a1_text"         text[] GENERATED ALWAYS AS (jsonb_array_to_text_array(metadata -> 'A1_TEXT')) STORED,
    "time_text"       text GENERATED ALWAYS AS (metadata ->> 'TIME_TEXT') STORED,
    "loc_text"        text GENERATED ALWAYS AS (metadata ->> 'LOC_TEXT') STORED,
    "a0_id"           text[] GENERATED ALWAYS AS (jsonb_array_to_text_array(metadata -> 'A0')) STORED,
    "a1_id"           text[] GENERATED ALWAYS AS (jsonb_array_to_text_array(metadata -> 'A1')) STORED,
    "time_id"         text GENERATED ALWAYS AS (metadata ->> 'TIME') STORED,
    "loc_id"          text GENERATED ALWAYS AS (metadata ->> 'LOC') STORED,
    "created_at"      timestamp DEFAULT now(),
    "updated_at"      timestamp DEFAULT now()
) PARTITION BY HASH (id);

CREATE TABLE IF NOT EXISTS text_annotations_p1 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 0);
CREATE TABLE IF NOT EXISTS text_annotations_p2 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 1);
CREATE TABLE IF NOT EXISTS text_annotations_p3 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 2);
CREATE TABLE IF NOT EXISTS text_annotations_p4 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 3);
CREATE TABLE IF NOT EXISTS text_annotations_p5 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 4);
CREATE TABLE IF NOT EXISTS text_annotations_p6 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 5);
CREATE TABLE IF NOT EXISTS text_annotations_p7 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 6);
CREATE TABLE IF NOT EXISTS text_annotations_p8 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 7);
CREATE TABLE IF NOT EXISTS text_annotations_p9 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 8);
CREATE TABLE IF NOT EXISTS text_annotations_p10 PARTITION OF text_annotations FOR VALUES WITH (modulus 10, remainder 9);


DROP TABLE IF EXISTS "text" CASCADE;
CREATE TABLE "text"
(
    "id"         text PRIMARY KEY              NOT NULL,
    "text"       text                          NOT NULL,
    "embedding"  halfvec(384)                  NOT NULL,
    "doc_id"     text                          NOT NULL,
    "metadata"   jsonb     DEFAULT '{}'::jsonb NOT NULL,
    "created_at" timestamp DEFAULT now(),
    "updated_at" timestamp DEFAULT now()
);

CREATE TYPE "public"."sentimentEnum" AS ENUM ('positive', 'negative', 'neutral');
DROP TABLE IF EXISTS "claims" CASCADE;
CREATE TABLE "claims"
(
    "id"         uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "doc_id"     text                                       NOT NULL,
    "claim"      text                                       NOT NULL,
    "claim_type" text                                       NOT NULL,
    "source"     text,
    "subject"    text                                       NOT NULL,
    "predicate"  text                                       NOT NULL,
    "object"     text                                       NOT NULL,
    "stance"     text                                       NOT NULL,
    "certainty"  text                                       NOT NULL,
    "modality"   text                                       NOT NULL,
    "negation"   boolean                                    NOT NULL,
    "condition"  text                                       NOT NULL,
    "time"       text                                       NOT NULL,
    "location"   text                                       NOT NULL,
    "evidence"   text                                       NOT NULL,
    "sentiment"  "sentimentEnum"                            NOT NULL,
    "keywords"   text[]                                     NOT NULL,
    "embedding"  halfvec(384)                               NOT NULL,
    "created_at" timestamp        DEFAULT now(),
    "updated_at" timestamp        DEFAULT now()
);


DROP TABLE IF EXISTS "annotation_to_ontology" CASCADE;
CREATE TABLE "annotation_to_ontology"
(
    "id"                    serial PRIMARY KEY NOT NULL,
    "ontology_id"           integer            NOT NULL,
    "annotation_type_value" text               NOT NULL,
    CONSTRAINT "ato_ont_type_idx" UNIQUE ("ontology_id", "annotation_type_value")
);

DROP TABLE IF EXISTS "ontology" CASCADE;
CREATE TABLE "ontology"
(
    "id"           serial PRIMARY KEY      NOT NULL,
    "name"         text                    NOT NULL,
    "parent_id"    integer,
    "description"  text,
    "color"        text    DEFAULT 'SLATE' NOT NULL,
    "is_attribute" boolean DEFAULT false   NOT NULL,
    "path"         "ltree"                 NOT NULL,
    "properties"   jsonb   DEFAULT '{}'::jsonb,
    CONSTRAINT "ontology_name_unique" UNIQUE ("name")
);

DROP TABLE IF EXISTS "jobs" CASCADE;
CREATE TABLE "jobs"
(
    "id"           serial PRIMARY KEY              NOT NULL,
    "name"         varchar(255)                    NOT NULL,
    "apiKey"       text,
    "user_id"      text                            NOT NULL,
    "status"       "job_status" DEFAULT 'waiting'  NOT NULL,
    "job_type"     "job_type"   DEFAULT 'other'    NOT NULL,
    "total"        integer      DEFAULT 0          NOT NULL,
    "completed"    integer      DEFAULT 0          NOT NULL,
    "failed"       integer      DEFAULT 0          NOT NULL,
    "metadata"     json         DEFAULT '{}'::json NOT NULL,
    "created_at"   timestamp    DEFAULT now(),
    "started_at"   timestamp,
    "completed_at" timestamp,
    "updated_at"   timestamp    DEFAULT now()
);

DROP TABLE IF EXISTS "configuration" CASCADE;
CREATE TABLE "configuration"
(
    "name"  text PRIMARY KEY NOT NULL,
    "value" jsonb            NOT NULL
);

DROP TABLE IF EXISTS "topics" CASCADE;
CREATE TABLE "topics"
(
    "id"          text PRIMARY KEY        NOT NULL,
    "name"        text                    NOT NULL,
    "is_fixed"    boolean   DEFAULT false NOT NULL,
    "embedding"   halfvec(384)            NOT NULL,
    "support"     integer   DEFAULT 0     NOT NULL,
    "doc_support" integer   DEFAULT 0     NOT NULL,
    "created_at"  timestamp DEFAULT now(),
    "updated_at"  timestamp DEFAULT now()
);

DROP TABLE IF EXISTS "topics_tree" CASCADE;
CREATE TABLE "topics_tree"
(
    "id"         text PRIMARY KEY NOT NULL,
    "name"       text             NOT NULL,
    "parent_id"  text,
    "is_leaf"    boolean   DEFAULT false,
    "level"      integer,
    "split_k"    integer,
    "created_at" timestamp DEFAULT now(),
    "updated_at" timestamp DEFAULT now()
);

DROP TABLE IF EXISTS "topic_tree_topic_map" CASCADE;
CREATE TABLE "topic_tree_topic_map"
(
    "id"       serial PRIMARY KEY NOT NULL,
    "node_id"  text,
    "topic_id" text
);

DROP TABLE IF EXISTS "metadata" CASCADE;
CREATE TABLE "metadata"
(
    "id"                   uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "source"               "metadata_sources"                         NOT NULL,
    "name"                 text                                       NOT NULL,
    "data_type"            "metadata_data_type"                       NOT NULL,
    "formatter"            text,
    "links_to_document_id" boolean          DEFAULT false             NOT NULL,
    "metadata_link"        uuid,
    CONSTRAINT "source_name_unique" UNIQUE ("source", "name")
);

DROP TABLE IF EXISTS "keywords" CASCADE;
CREATE TABLE "keywords"
(
    "id"          uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "category"    text,
    "keyword"     text                                       NOT NULL,
    "document_id" text                                       NOT NULL,
    "text_id"     text                                       NOT NULL,
    "embedding"   halfvec(384)                               NOT NULL
);

DROP TABLE IF EXISTS "precomputed_stats" CASCADE;
CREATE TABLE "precomputed_stats"
(
    id    SERIAL PRIMARY KEY,
    name  TEXT  NOT NULL,
    value JSONB NOT NULL
);


ALTER TABLE "keywords"
    DROP CONSTRAINT IF EXISTS "keywords_document_id_documents_id_fk";
ALTER TABLE "keywords"
    ADD CONSTRAINT "keywords_document_id_documents_id_fk" FOREIGN KEY ("document_id") REFERENCES "public"."documents" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "keywords"
    DROP CONSTRAINT IF EXISTS "keywords_text_id_text_id_fk";
ALTER TABLE "keywords"
    ADD CONSTRAINT "keywords_text_id_text_id_fk" FOREIGN KEY ("text_id") REFERENCES "public"."text" ("id") ON DELETE cascade ON UPDATE no action;


ALTER TABLE "account"
    DROP CONSTRAINT IF EXISTS "account_user_id_user_id_fk";
ALTER TABLE "account"
    ADD CONSTRAINT "account_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "apikey"
    DROP CONSTRAINT IF EXISTS "apikey_user_id_user_id_fk";
ALTER TABLE "apikey"
    ADD CONSTRAINT "apikey_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "session"
    DROP CONSTRAINT IF EXISTS "session_user_id_user_id_fk";
ALTER TABLE "session"
    ADD CONSTRAINT "session_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "text_annotations"
    DROP CONSTRAINT IF EXISTS "text_annotations_text_id_text_id_fk";
ALTER TABLE "text_annotations"
    ADD CONSTRAINT "text_annotations_text_id_text_id_fk" FOREIGN KEY ("text_id") REFERENCES "public"."text" ("id") ON DELETE cascade ON UPDATE no action;


ALTER TABLE "text_annotations"
    DROP CONSTRAINT IF EXISTS "text_annotations_doc_id_documents_id_fk";
ALTER TABLE "text_annotations"
    ADD CONSTRAINT "text_annotations_doc_id_documents_id_fk" FOREIGN KEY ("doc_id") REFERENCES "public"."documents" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "text"
    DROP CONSTRAINT IF EXISTS "text_doc_id_documents_id_fk";
ALTER TABLE "text"
    ADD CONSTRAINT "text_doc_id_documents_id_fk" FOREIGN KEY ("doc_id") REFERENCES "public"."documents" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "annotation_to_ontology"
    DROP CONSTRAINT IF EXISTS "annotation_to_ontology_ontology_id_ontology_id_fk";
ALTER TABLE "annotation_to_ontology"
    ADD CONSTRAINT "annotation_to_ontology_ontology_id_ontology_id_fk" FOREIGN KEY ("ontology_id") REFERENCES "public"."ontology" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "jobs"
    DROP CONSTRAINT IF EXISTS "jobs_user_id_user_id_fk";
ALTER TABLE "jobs"
    ADD CONSTRAINT "jobs_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user" ("id") ON DELETE cascade ON UPDATE no action;


ALTER TABLE "topic_tree_topic_map"
    DROP CONSTRAINT IF EXISTS "topic_tree_topic_map_node_id_topics_tree_id_fk";
ALTER TABLE "topic_tree_topic_map"
    ADD CONSTRAINT "topic_tree_topic_map_node_id_topics_tree_id_fk" FOREIGN KEY ("node_id") REFERENCES "public"."topics_tree" ("id") ON DELETE cascade ON UPDATE no action;

ALTER TABLE "topic_tree_topic_map"
    DROP CONSTRAINT IF EXISTS "topic_tree_topic_map_topic_id_topics_id_fk";
ALTER TABLE "topic_tree_topic_map"
    ADD CONSTRAINT "topic_tree_topic_map_topic_id_topics_id_fk" FOREIGN KEY ("topic_id") REFERENCES "public"."topics" ("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint


CREATE INDEX IF NOT EXISTS "document_metadata_gin_idx" ON "documents" USING gin ("metadata" jsonb_path_ops);

CREATE INDEX IF NOT EXISTS text_annotations_sentence_aid_idx ON text_annotations USING btree (sentence_aid);
CREATE INDEX IF NOT EXISTS "text_annotation_normalized_index" ON "text_annotations" USING btree ("normalized_text");
CREATE INDEX IF NOT EXISTS "text_annotation_sentence_aid_index" ON "text_annotations" USING btree ("sentence_aid");
CREATE INDEX IF NOT EXISTS "text_annotation_document_id_index" ON "text_annotations" USING btree ("doc_id");
CREATE INDEX IF NOT EXISTS "text_annotation_mapping_index" ON "text_annotations" USING btree ("mapping");
CREATE INDEX IF NOT EXISTS "ml_text_annotation_search_index" ON "text_annotations" USING pgroonga ("text");
CREATE INDEX IF NOT EXISTS "text_annotation_embedding_index" ON "text_annotations" USING hnsw ("embedding" halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS "text_annotation_metadata_gin_idx" ON "text_annotations" USING gin ("metadata" jsonb_path_ops);
CREATE INDEX IF NOT EXISTS "text_annotation_a0_text_index" on "text_annotations" USING gin ("a0_text");
CREATE INDEX IF NOT EXISTS text_annotations_a0_lower_idx ON text_annotations USING GIN (lower_array(a0_text));
CREATE INDEX IF NOT EXISTS "text_annotation_a1_text_index" on "text_annotations" USING gin ("a1_text");
CREATE INDEX IF NOT EXISTS text_annotations_a1_lower_idx ON text_annotations USING GIN (lower_array(a1_text));
CREATE INDEX IF NOT EXISTS "text_annotation_time_text_index" ON "text_annotations" USING btree ("time_text");
CREATE INDEX IF NOT EXISTS "text_annotation_loc_text_index" ON "text_annotations" USING btree ("loc_text");

CREATE INDEX IF NOT EXISTS "ml_text_search_index" ON "text" USING pgroonga ("text");
CREATE INDEX IF NOT EXISTS "text_document_id_index" ON "text" USING btree ("doc_id");
CREATE INDEX IF NOT EXISTS "text_embedding_index" ON "text" USING hnsw ("embedding" halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS "text_metadata_gin_idx" ON "text" USING gin ("metadata" jsonb_path_ops);
CREATE INDEX IF NOT EXISTS "ato_ont_id" ON "annotation_to_ontology" USING btree ("ontology_id");
CREATE INDEX IF NOT EXISTS "ato_ont_type" ON "annotation_to_ontology" USING btree ("annotation_type_value");
CREATE INDEX IF NOT EXISTS "idx_ontology_parent_id" ON "ontology" USING btree ("parent_id");
CREATE INDEX IF NOT EXISTS "idx_ontology_name" ON "ontology" USING btree ("name");
CREATE INDEX IF NOT EXISTS "idx_ontology_path_gist" ON "ontology" USING GIST ("path");
CREATE INDEX IF NOT EXISTS "topics_embeddingIndex" ON "topics" USING hnsw ("embedding" halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS "metadata_link_index" on "metadata" USING btree ("links_to_document_id");
CREATE INDEX IF NOT EXISTS "keywords_embedding_index" ON "keywords" USING hnsw ("embedding" halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS "keywords_document_id" ON "keywords" USING btree ("document_id");
CREATE INDEX IF NOT EXISTS "keywords_category_idx" ON "keywords" USING btree ("category");

CREATE INDEX "topic_tree_parent_id" ON "topics_tree" USING btree ("id");

CREATE INDEX IF NOT EXISTS "claims_content_fts_index" ON "claims" USING pgroonga ("claim");
CREATE INDEX IF NOT EXISTS "claims_doc_id_idx" ON "claims" USING btree ("doc_id");
CREATE INDEX IF NOT EXISTS "claims_embedding_index" ON "claims" USING hnsw ("embedding" halfvec_cosine_ops);


CREATE UNIQUE INDEX IF NOT EXISTS "precomputed_stats_name_unique" ON "precomputed_stats" USING btree ("name");

DROP VIEW IF EXISTS "public"."annotation_with_ontology" CASCADE;
CREATE VIEW "public"."annotation_with_ontology" AS
(
select "text_annotations".*,
       "Lp_LGMVaYx"."path",
       "Lp_LGMVaYx"."name",
       "Lp_LGMVaYx"."color",
       "Lp_LGMVaYx"."properties",
       CONCAT("normalized_text", '-', "path") as "normalized_path"
from "text_annotations"
         inner join (select "ontology"."path",
                            "ontology"."name",
                            "ontology"."color",
                            "ontology"."properties",
                            "annotation_to_ontology"."annotation_type_value"
                     from "ontology"
                              inner join "annotation_to_ontology"
                                         on "ontology"."id" = "annotation_to_ontology"."ontology_id") "Lp_LGMVaYx"
                    on "text_annotations"."mapping" = "Lp_LGMVaYx"."annotation_type_value");


CREATE MATERIALIZED VIEW IF NOT EXISTS "public"."topic_sentences" AS
(
select "topics"."id"                                                                               as "topic_id",
       "text_annotations"."doc_id",
       "text_annotations"."text_id",
       "text_annotations"."sentence_aid",
       "text_annotations"."text"                                                                   as "sentence",
       (1 - cosine_distance("topics"."embedding", "text_annotations"."embedding"::halfvec)::float) as "similarity"
from "topics"
         inner join "text_annotations" on "text_annotations"."type" = 'sentence'
where (1 - cosine_distance("topics"."embedding", "text_annotations"."embedding"::halfvec)::float) >= 0.65)
WITH DATA;

CREATE INDEX IF NOT EXISTS topic_sentences_sentence_aid ON topic_sentences (sentence_aid);
CREATE INDEX IF NOT EXISTS topic_sentences_topic_id ON topic_sentences (topic_id);
CREATE INDEX IF NOT EXISTS topic_sentences_text_id ON topic_sentences (text_id);
CREATE UNIQUE INDEX IF NOT EXISTS topic_sentences_sentence_topic_id ON topic_sentences (sentence_aid, topic_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS "public"."concept_co_occurrence" AS
(
WITH keyword_doc_counts AS (SELECT category, COUNT(document_id) as count
                            FROM keywords
                            where category is not null
                            group by category
                            having COUNT(document_id) > 5),
     keyword_documents as (select distinct a.category, document_id, b.count
                           from keywords a
                                    inner join keyword_doc_counts b on a.category = b.category
                           where a.category is not null)
SELECT a.category    as source,
       b.category    as target,
       a.document_id as document_id,
       a.count       as source_count,
       b.count       as target_count
from keyword_documents as a
         inner join keyword_documents b on a.document_id = b.document_id and a.category != b.category
where a.category < b.category)
WITH DATA;


CREATE INDEX IF NOT EXISTS concept_co_occurrence_document_idx ON concept_co_occurrence (document_id);
CREATE UNIQUE INDEX IF NOT EXISTS concept_co_occurrence_source_target_idx ON concept_co_occurrence (source, target, document_id);

DROP VIEW IF EXISTS document_topic_concepts;
CREATE VIEW document_topic_concepts AS
(
WITH TOPIC_DOCUMENTS AS (SELECT DISTINCT topic_id, doc_id
                         FROM topic_sentences),
     CONCEPTS AS (SELECT category    AS concept,
                         document_id AS doc_id,
                         keyword
                  FROM keywords
                  WHERE category IS NOT NULL),
     TOPIC_TOTALS AS (SELECT topic_id, COUNT(DISTINCT doc_id) AS topic_count
                      FROM TOPIC_DOCUMENTS
                      GROUP BY topic_id),
     CONCEPT_TOTALS AS (SELECT concept, COUNT(DISTINCT doc_id) AS concept_count
                        FROM CONCEPTS
                        GROUP BY concept),
-- 1. Base overlapping data
     OVERLAPPING_DOCS AS (SELECT t.topic_id,
                                 c.concept,
                                 t.doc_id,
                                 c.keyword
                          FROM TOPIC_DOCUMENTS t
                                   JOIN CONCEPTS c ON t.doc_id = c.doc_id),
-- 2. Calculate the overlap count safely away from the JSON
     OVERLAP_COUNTS AS (SELECT topic_id,
                               concept,
                               COUNT(DISTINCT doc_id) AS overlap_count
                        FROM OVERLAPPING_DOCS
                        GROUP BY topic_id, concept),
-- 3. Package the JSON instances
     KEYWORD_ROLLUP AS (SELECT topic_id,
                               concept,
                               json_object_agg(keyword, kw_count) AS instances
                        FROM (SELECT topic_id,
                                     concept,
                                     keyword,
                                     COUNT(DISTINCT doc_id) AS kw_count
                              FROM OVERLAPPING_DOCS
                              GROUP BY topic_id, concept, keyword) sub
                        GROUP BY topic_id, concept)
-- 4. Bring it all together (No GROUP BY needed here!)
SELECT oc.topic_id,
       t.name as topic,
       tt.topic_count,
       oc.concept,
       ct.concept_count,
       oc.overlap_count,
       kr.instances
FROM OVERLAP_COUNTS oc
         JOIN TOPICS t on t.id = oc.topic_id
         JOIN TOPIC_TOTALS tt ON oc.topic_id = tt.topic_id
         JOIN CONCEPT_TOTALS ct ON oc.concept = ct.concept
         JOIN KEYWORD_ROLLUP kr ON oc.topic_id = kr.topic_id AND oc.concept = kr.concept
ORDER BY oc.overlap_count DESC
    );



CREATE OR REPLACE FUNCTION get_topic_tree(p_id TEXT DEFAULT NULL)
    RETURNS JSONB AS
$$
DECLARE
    _result JSONB;
BEGIN
    SELECT jsonb_agg(
                   jsonb_build_object(
                           'id', t.id,
                           'name', t.name,
                           'parent_id', t.parent_id,
                           'topics', json_array(SELECT jsonb_build_object(
                                                               'id', topic.id,
                                                               'name', topic.name,
                                                               'support', topic.support,
                                                               'doc_support', topic.doc_support
                                                       )
                                                FROM topic_tree_topic_map tttmp
                                                         inner join topics topic on tttmp.topic_id = topic.id
                                                WHERE tttmp.node_id = t.id),
                           'children', (SELECT COALESCE(jsonb_agg(child_res), '[]'::jsonb)
                                        FROM (SELECT get_tree_json(t.id) as child_res
                                              FROM topics_tree
                                              WHERE parent_id = t.id) sub)
                   )
           )
    INTO _result
    FROM topics_tree t
    WHERE t.parent_id IS NOT DISTINCT FROM p_id;
    RETURN COALESCE(_result, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql;