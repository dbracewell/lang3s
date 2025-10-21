CREATE TABLE "documents" (
	"id" text PRIMARY KEY NOT NULL,
	"title" text NOT NULL,
	"metadata" json DEFAULT '{}'::json NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "text_annotations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"text" text NOT NULL,
	"text_id" text NOT NULL,
	"doc_id" text NOT NULL,
	"start" integer NOT NULL,
	"end" integer NOT NULL,
	"type" text NOT NULL,
	"value" text NOT NULL,
	"embedding" vector(384) NOT NULL,
	"metadata" json DEFAULT '{}'::json NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "text" (
	"id" text PRIMARY KEY NOT NULL,
	"text" text NOT NULL,
	"embedding" vector(384) NOT NULL,
	"doc_id" text NOT NULL,
	"metadata" json DEFAULT '{}'::json NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
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
--> statement-breakpoint
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
--> statement-breakpoint
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
--> statement-breakpoint
CREATE TABLE "verification" (
	"id" text PRIMARY KEY NOT NULL,
	"identifier" text NOT NULL,
	"value" text NOT NULL,
	"expires_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "text_annotations" ADD CONSTRAINT "text_annotations_text_id_text_id_fk" FOREIGN KEY ("text_id") REFERENCES "public"."text"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "text_annotations" ADD CONSTRAINT "text_annotations_doc_id_documents_id_fk" FOREIGN KEY ("doc_id") REFERENCES "public"."documents"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "text" ADD CONSTRAINT "text_doc_id_documents_id_fk" FOREIGN KEY ("doc_id") REFERENCES "public"."documents"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "account" ADD CONSTRAINT "account_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "session" ADD CONSTRAINT "session_user_id_user_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "text_annotation_start_idx" ON "text_annotations" USING btree ("start");--> statement-breakpoint
CREATE INDEX "text_annotation_end_idx" ON "text_annotations" USING btree ("end");--> statement-breakpoint
CREATE INDEX "text_annotation_type_idx" ON "text_annotations" USING btree ("type");--> statement-breakpoint
CREATE INDEX "text_annotation_value_idx" ON "text_annotations" USING btree ("value");--> statement-breakpoint
CREATE INDEX "text_annotation_text_search_index" ON "text_annotations" USING gin (to_tsvector('english', "text"));--> statement-breakpoint
CREATE INDEX "embeddingIndex" ON "text_annotations" USING hnsw ("embedding" vector_cosine_ops);--> statement-breakpoint
CREATE INDEX "text_search_index" ON "text" USING gin (to_tsvector('english', "text"));--> statement-breakpoint
CREATE INDEX "text_embeddingIndex" ON "text" USING hnsw ("embedding" vector_cosine_ops);