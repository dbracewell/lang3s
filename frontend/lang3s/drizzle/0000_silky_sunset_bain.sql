-- Custom SQL migration file, put your code below! --
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;
CREATE EXTENSION IF NOT EXISTS ltree;


CREATE TYPE "public"."job_status" AS ENUM('waiting', 'processing', 'complete', 'failed');
CREATE TABLE "annotation_to_ontology" (
	"id" serial PRIMARY KEY NOT NULL,
	"ontology_id" text NOT NULL,
	"annotation_type_value" text NOT NULL,
	CONSTRAINT "ato_ont_type_idx" UNIQUE("ontology_id","annotation_type_value")
);

CREATE TABLE "documents" (
	"id" text PRIMARY KEY NOT NULL,
	"title" text NOT NULL,
	"metadata" json DEFAULT '{}'::json NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);

CREATE TABLE "jobs" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(255) NOT NULL,
	"apiKey" text,
	"user_id" text,
	"status" "job_status" DEFAULT 'waiting' NOT NULL,
	"total" integer DEFAULT 0 NOT NULL,
	"completed" integer DEFAULT 0 NOT NULL,
	"failed" integer DEFAULT 0 NOT NULL,
	"metadata" json DEFAULT '{}'::json NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"started_at" timestamp,
	"completed_at" timestamp,
	"updated_at" timestamp DEFAULT now()
);

CREATE TABLE "ontology" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"parent_id" integer,
	"description" text,
	"is_attribute" boolean DEFAULT false NOT NULL,
	"path" "ltree" NOT NULL,
	"properties" jsonb DEFAULT '{}'::jsonb,
	CONSTRAINT "ontology_name_unique" UNIQUE("name")
);

CREATE TABLE "text_annotations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"text" text NOT NULL,
	"text_id" text NOT NULL,
	"doc_id" text NOT NULL,
	"start" integer NOT NULL,
	"end" integer NOT NULL,
	"type" text NOT NULL,
	"value" text NOT NULL,
	"embedding" vector(768),
	"metadata" json DEFAULT '{}'::json NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);

CREATE TABLE "text" (
	"id" text PRIMARY KEY NOT NULL,
	"text" text NOT NULL,
	"embedding" vector(768) NOT NULL,
	"doc_id" text NOT NULL,
	"metadata" json DEFAULT '{}'::json NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);

CREATE TABLE "account" (
	"id" text PRIMARY KEY NOT NULL,
	"account_id" text NOT NULL,
	"provider_id" text NOT NULL,
	"user_id" text NOT NULL,
	"access_token" text,
	"refresh_token" text,
	"id_token" text,
	"access_token_expires_at" timestamp,
	"refresh_token_expires_at" timestamp,
	"scope" text,
	"password" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp NOT NULL
);

CREATE TABLE "session" (
	"id" text PRIMARY KEY NOT NULL,
	"expires_at" timestamp NOT NULL,
	"token" text NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp NOT NULL,
	"ip_address" text,
	"user_agent" text,
	"user_id" text NOT NULL,
	"impersonated_by" text,
	CONSTRAINT "session_token_unique" UNIQUE("token")
);

CREATE TABLE "user" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"email" text NOT NULL,
	"email_verified" boolean DEFAULT false NOT NULL,
	"image" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	"role" text,
	"banned" boolean DEFAULT false,
	"ban_reason" text,
	"ban_expires" timestamp,
	"username" text,
	"display_username" text,
	CONSTRAINT "user_email_unique" UNIQUE("email"),
	CONSTRAINT "user_username_unique" UNIQUE("username")
);

CREATE TABLE "verification" (
	"id" text PRIMARY KEY NOT NULL,
	"identifier" text NOT NULL,
	"value" text NOT NULL,
	"expires_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);

ALTER TABLE "jobs" ADD CONSTRAINT "jobs_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;
ALTER TABLE "text_annotations" ADD CONSTRAINT "text_annotations_text_id_text_id_fk" FOREIGN KEY ("text_id") REFERENCES "public"."text"("id") ON DELETE cascade ON UPDATE no action;
ALTER TABLE "text_annotations" ADD CONSTRAINT "text_annotations_doc_id_documents_id_fk" FOREIGN KEY ("doc_id") REFERENCES "public"."documents"("id") ON DELETE cascade ON UPDATE no action;
ALTER TABLE "text" ADD CONSTRAINT "text_doc_id_documents_id_fk" FOREIGN KEY ("doc_id") REFERENCES "public"."documents"("id") ON DELETE cascade ON UPDATE no action;
ALTER TABLE "account" ADD CONSTRAINT "account_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;
ALTER TABLE "session" ADD CONSTRAINT "session_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;
CREATE INDEX "ato_ont_id" ON "annotation_to_ontology" USING btree ("ontology_id");
CREATE INDEX "ato_ont_type" ON "annotation_to_ontology" USING btree ("annotation_type_value");

CREATE INDEX "idx_ontology_parent_id" ON "ontology" USING btree ("parent_id");
CREATE INDEX "idx_ontology_name" ON "ontology" USING btree ("name");
CREATE INDEX "idx_ontology_path_gist" ON "ontology" USING GIST ("path");
CREATE INDEX "idx_ontology_properties_gin" ON "ontology" USING GIN ("properties" jsonb_path_ops);

CREATE INDEX "text_annotation_start_idx" ON "text_annotations" USING btree ("start");
CREATE INDEX "text_annotation_end_idx" ON "text_annotations" USING btree ("end");
CREATE INDEX "text_annotation_type_idx" ON "text_annotations" USING btree ("type");
CREATE INDEX "text_annotation_value_idx" ON "text_annotations" USING btree ("value");
CREATE INDEX "ml_text_annotation_search_index" ON "text_annotations" USING pgroonga ("text");
CREATE INDEX "embeddingIndex" ON "text_annotations" USING hnsw ("embedding" vector_cosine_ops);
CREATE INDEX "ml_text_search_index" ON "text" USING pgroonga ("text");
CREATE INDEX "text_embeddingIndex" ON "text" USING hnsw ("embedding" vector_cosine_ops);