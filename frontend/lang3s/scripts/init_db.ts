import { db } from "@/lib/db";
import { MetadataTable } from "@/lib/db/schemas/metadata";
import { sql } from "drizzle-orm";
import { TopicDocuments, TopicSentences } from "@/lib/db/schemas/views";

db.insert(MetadataTable)
  .values([
    {
      source: "document",
      name: "language",
      dataType: "string",
    },
    {
      source: "document",
      name: "mime-type",
      dataType: "string",
    },
  ])
  .execute();

db.execute(
  sql`CREATE INDEX topic_sentences_sentence_aid ON ${TopicSentences} (${TopicSentences.sentenceAid})`,
);

db.execute(
  sql`CREATE INDEX topic_sentences_topic_id ON ${TopicSentences} (${TopicSentences.topicId})`,
);

db.execute(
  sql`CREATE INDEX topic_sentences_text_id ON ${TopicSentences} (${TopicSentences.textId})`,
);

db.execute(
  sql`CREATE UNIQUE INDEX topic_sentences_sentence_topic_id ON ${TopicSentences} (${TopicSentences.sentenceAid},${TopicSentences.topicId})`,
);

db.execute(
  sql`CREATE INDEX topic_documents_topic_id ON ${TopicDocuments} (${TopicDocuments.topicId})`,
);

db.execute(
  sql`CREATE INDEX topic_documents_text_id ON ${TopicDocuments} (${TopicDocuments.textId})`,
);

db.execute(
  sql`CREATE UNIQUE INDEX topic_documents_topic_text_id ON ${TopicDocuments} (${TopicDocuments.textId},${TopicDocuments.topicId})`,
);
