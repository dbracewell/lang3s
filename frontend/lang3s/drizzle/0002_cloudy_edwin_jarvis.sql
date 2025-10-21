DROP INDEX "text_annotation_text_search_index";--> statement-breakpoint
DROP INDEX "text_search_index";--> statement-breakpoint
ALTER TABLE "text_annotations" ALTER COLUMN "embedding" SET DATA TYPE vector(300);--> statement-breakpoint
ALTER TABLE "text" ALTER COLUMN "embedding" SET DATA TYPE vector(300);--> statement-breakpoint
CREATE INDEX "ml_text_annotation_search_index" ON "text_annotations" USING pgroonga ("text");--> statement-breakpoint
CREATE INDEX "ml_text_search_index" ON "text" USING pgroonga ("text");