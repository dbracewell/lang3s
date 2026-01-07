-- Custom SQL migration file, put your code below! --
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;
CREATE EXTENSION IF NOT EXISTS ltree;

DROP TYPE IF EXISTS "public"."job_status" CASCADE;
DROP TYPE IF EXISTS "public"."metadata_data_type" CASCADE;
DROP TYPE IF EXISTS "public"."metadata_sources" CASCADE;
CREATE TYPE "public"."job_status" AS ENUM ('waiting', 'processing', 'complete', 'failed');
CREATE TYPE "public"."job_type" AS ENUM ('annotation', 'update', 'other');
CREATE TYPE "public"."metadata_data_type" AS ENUM ('string', 'int', 'float', 'boolean', 'date', 'datetime');
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

CREATE TABLE IF NOT EXISTS "documents"
(
    "id"         text PRIMARY KEY              NOT NULL,
    "title"      text                          NOT NULL,
    "metadata"   jsonb     DEFAULT '{}'::jsonb NOT NULL,
    "created_at" timestamp DEFAULT now(),
    "updated_at" timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "text_annotations"
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


CREATE TABLE IF NOT EXISTS "text"
(
    "id"         text PRIMARY KEY              NOT NULL,
    "text"       text                          NOT NULL,
    "embedding"  halfvec(384)                  NOT NULL,
    "doc_id"     text                          NOT NULL,
    "metadata"   jsonb     DEFAULT '{}'::jsonb NOT NULL,
    "created_at" timestamp DEFAULT now(),
    "updated_at" timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "annotation_to_ontology"
(
    "id"                    serial PRIMARY KEY NOT NULL,
    "ontology_id"           integer            NOT NULL,
    "annotation_type_value" text               NOT NULL,
    CONSTRAINT "ato_ont_type_idx" UNIQUE ("ontology_id", "annotation_type_value")
);

CREATE TABLE IF NOT EXISTS "ontology"
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

CREATE TABLE IF NOT EXISTS "jobs"
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

CREATE TABLE IF NOT EXISTS "configuration"
(
    "name"  text PRIMARY KEY NOT NULL,
    "value" jsonb            NOT NULL
);

CREATE TABLE IF NOT EXISTS "topics"
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

CREATE TABLE IF NOT EXISTS "metadata"
(
    "id"        uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "source"    "metadata_sources"                         NOT NULL,
    "name"      text                                       NOT NULL,
    "data_type" "metadata_data_type"                       NOT NULL,
    "formatter" text,
    CONSTRAINT "source_name_unique" UNIQUE ("source", "name")
);

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


CREATE INDEX IF NOT EXISTS "document_metadata_gin_idx" ON "documents" USING gin ("metadata" jsonb_path_ops);
CREATE INDEX IF NOT EXISTS "text_annotation_normalized_index" ON "text_annotations" USING btree ("normalized_text");
CREATE INDEX IF NOT EXISTS "text_annotation_sentence_aid_index" ON "text_annotations" USING btree ("sentence_aid");
CREATE INDEX IF NOT EXISTS "text_annotation_document_id_index" ON "text_annotations" USING btree ("doc_id");
CREATE INDEX IF NOT EXISTS "text_annotation_mapping_index" ON "text_annotations" USING btree ("mapping");
CREATE INDEX IF NOT EXISTS "ml_text_annotation_search_index" ON "text_annotations" USING pgroonga ("text");
CREATE INDEX IF NOT EXISTS "text_annotation_embedding_index" ON "text_annotations" USING hnsw ("embedding" halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS "text_annotation_metadata_gin_idx" ON "text_annotations" USING gin ("metadata" jsonb_path_ops);
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

DROP VIEW IF EXISTS "public"."annotation_with_ontology" CASCADE;
CREATE VIEW "public"."annotation_with_ontology" AS
(
select "text_annotations".*,
       "text_annotations"."metadata" -> 'A0_TEXT'   as "A0",
       "text_annotations"."metadata" -> 'A1_TEXT'   as "A1",
       "text_annotations"."metadata" -> 'TIME_TEXT' as "TIME",
       "text_annotations"."metadata" -> 'LOC_TEXT'  as "LOCATION",
       "Lp_LGMVaYx"."path",
       "Lp_LGMVaYx"."name",
       "Lp_LGMVaYx"."color",
       "Lp_LGMVaYx"."properties",
       CONCAT("normalized_text", '-', "path")       as "normalized_path"
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
       (1 - cosine_distance("topics"."embedding", "text_annotations"."embedding"::halfvec)::float) as "similarity"
from "topics"
         inner join "text_annotations" on "text_annotations"."type" = 'sentence'
where (1 - cosine_distance("topics"."embedding", "text_annotations"."embedding"::halfvec)::float) >= 0.65)
WITH DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS "public"."topic_documents" AS
(
select "topic_id", "doc_id", "text_id", AVG("similarity") as "similarity", count(distinct "sentence_aid") as "score"
from "topic_sentences"
group by "topic_sentences"."doc_id", "topic_sentences"."text_id", "topic_id"
having count(distinct "topic_sentences"."sentence_aid") > 2)
WITH DATA;

CREATE MATERIALIZED VIEW "public"."annotation_counts" AS
(
select "normalized_text",
       "path",
       count(distinct "doc_id")       as "document_count",
       count(distinct "sentence_aid") as "sentence_count",
       count(*)                       as "mention_count"
from "annotation_with_ontology"
where "path" <@ 'ALL.Entity'
group by "normalized_text", "annotation_with_ontology"."path"
having count(distinct "doc_id") >= 5)
WITH DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS "public"."annotation_co_occurrence" AS
(
SELECT t1.normalized_text              as "source",
       t2.normalized_text              as "target",
       t1.path                         as "source_type",
       t2.path                         as "target_type",
       count(distinct t1.doc_id)       as "document_count",
       count(distinct t1.sentence_aid) as "sentence_count"
FROM annotation_with_ontology t1
         INNER JOIN annotation_with_ontology t2 on t1.doc_id = t2.doc_id and t1.normalized_text < t2.normalized_text
WHERE t1."path" <@ 'ALL.Entity'
  and t2."path" <@ 'ALL.Entity'
GROUP BY 1, 2, 3, 4
HAVING count(distinct t1.doc_id) > 1
    )
WITH DATA;


CREATE UNIQUE INDEX IF NOT EXISTS annotation_counts_unique_idx ON annotation_counts (normalized_text, path);
CREATE UNIQUE INDEX IF NOT EXISTS annotation_co_occurrence_unique_idx ON annotation_co_occurrence (source, source_type, target, target_type);
CREATE INDEX IF NOT EXISTS topic_sentences_sentence_aid ON topic_sentences (sentence_aid);
CREATE INDEX IF NOT EXISTS topic_sentences_topic_id ON topic_sentences (topic_id);
CREATE INDEX IF NOT EXISTS topic_sentences_text_id ON topic_sentences (text_id);
CREATE UNIQUE INDEX IF NOT EXISTS topic_sentences_sentence_topic_id ON topic_sentences (sentence_aid, topic_id);
CREATE INDEX IF NOT EXISTS topic_documents_topic_id ON topic_documents (topic_id);
CREATE INDEX IF NOT EXISTS topic_documents_text_id ON topic_documents (text_id);
CREATE UNIQUE INDEX IF NOT EXISTS topic_documents_topic_text ON topic_documents (topic_id, text_id);

