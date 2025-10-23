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
--> statement-breakpoint
CREATE INDEX "idx_ontology_parent_id" ON "ontology" USING btree ("parent_id");--> statement-breakpoint
CREATE INDEX "idx_ontology_name" ON "ontology" USING btree ("name");--> statement-breakpoint
CREATE INDEX "idx_ontology_path_gist" ON "ontology" USING GIST ("path");
CREATE INDEX "idx_ontology_properties_gin" ON "ontology" USING GIN ("properties" jsonb_path_ops);