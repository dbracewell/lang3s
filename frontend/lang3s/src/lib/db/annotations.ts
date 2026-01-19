import {
  and,
  Column,
  eq,
  getTableColumns,
  ne,
  not,
  SQL,
  sql,
  type SQLWrapper,
} from "drizzle-orm";
import { TextAnnotationTable } from "@/lib/db/schemas/text";
import { coalesce, cosineSimilarity, jsonValue, upper } from "@/lib/db/funcs";
import { randomAlphaUnderscore } from "@/lib/utils/random";
import { AnnotationToOntology, OntologyTable } from "@/lib/db/schemas/ontology";
import { db } from "@/lib/db/index";
import { CoalesceArgument } from "@/lib/db/helpers/typing";

const EVENT_ARGS = {
  a0: sql<string[]>`${TextAnnotationTable.metadata}->'A0_TEXT'`.as("A0"),
  a1: sql<string[]>`${TextAnnotationTable.metadata}->'A1_TEXT'`.as("A1"),
  time: sql<string>`${TextAnnotationTable.metadata}->'TIME_TEXT'`.as("TIME"),
  location: sql<string>`${TextAnnotationTable.metadata}->'LOC_TEXT'`.as(
    "LOCATION",
  ),
};

// const FULL_TEXT_RANK = sql<number>`ROW_NUMBER() OVER (ORDER BY pgroonga_score(tableoid,ctid) DESC)`;
const FULL_TEXT_RANK = sql<number>`DENSE_RANK() OVER (ORDER BY pgroonga_score(tableoid,ctid) DESC)`;
const FULL_TEXT_SCORE = sql<number>`pgroonga_score(tableoid,ctid)`;
const BASE_ONTOLOGY_QUERY = db
  .select({
    ...getTableColumns(OntologyTable),
    mapping: AnnotationToOntology.annotation,
  })
  .from(AnnotationToOntology)
  .innerJoin(
    OntologyTable,
    eq(AnnotationToOntology.ontologyId, OntologyTable.id),
  );

interface ColumnOptions {
  includeEventArgs?: boolean;
  normalize?: boolean;
  includeFullTextScore?: boolean;
  includeFullTextRank?: boolean;
  similarTo?: number[] | Column | SQL.Aliased<number[]>;
}

type TextAnnotationTableColumns = (typeof TextAnnotationTable)["_"]["columns"];
type TextAnnotationTablePickedColumns<
  K extends keyof TextAnnotationTableColumns,
> = {
  [P in K]: TextAnnotationTableColumns[P];
};

type DynamicResult<
  T extends ColumnOptions,
  K extends keyof TextAnnotationTableColumns = never,
  A extends Record<string, SQL.Aliased> = {},
> = TextAnnotationTablePickedColumns<K> & {
  content: SQL.Aliased<string>;
} & A &
  (T["includeEventArgs"] extends true ? typeof EVENT_ARGS : {}) &
  (T["includeFullTextScore"] extends true
    ? { fullTextScore: SQL.Aliased<number> }
    : {}) &
  (T["includeFullTextRank"] extends true
    ? { fullTextRank: SQL.Aliased<number> }
    : {}) &
  (T["similarTo"] extends true
    ? { semanticScore: SQL.Aliased<number>; semanticRank: SQL.Aliased<number> }
    : {});

function _getDefaultColumns<
  T extends ColumnOptions,
  K extends keyof TextAnnotationTableColumns = never,
  A extends Record<string, SQL.Aliased> = {},
>({
  options,
  fields,
  computedColumns,
}: {
  options: T;
  fields?: K[];
  computedColumns?: A;
}): DynamicResult<T, K, A> {
  const {
    includeEventArgs = false,
    normalize = false,
    includeFullTextRank = false,
    includeFullTextScore = false,
    similarTo,
  } = options;
  let content = sql`${TextAnnotationTable.content}`;
  if (normalize) {
    content = upper(
      coalesce(
        jsonValue<string>(TextAnnotationTable.metadata, "coref_text"),
        jsonValue<string>(TextAnnotationTable.metadata, "lemma"),
        TextAnnotationTable.content,
      ),
    );
  }

  const allTableCols = getTableColumns(TextAnnotationTable);
  const keysToInclude = fields ?? [];

  const columns: any = computedColumns ?? {};
  keysToInclude.forEach((key) => {
    if (key !== "content" && columns[key] == null) {
      columns[key] = allTableCols[key as K];
    }
  });

  Object.assign(columns, { content: content.as(randomAlphaUnderscore()) });

  if (includeEventArgs) {
    Object.assign(columns, EVENT_ARGS);
  }

  if (includeFullTextRank) {
    Object.assign(columns, {
      fullTextRank: FULL_TEXT_RANK.as(randomAlphaUnderscore()),
    });
  }

  if (includeFullTextScore) {
    Object.assign(columns, {
      fullTextScore: FULL_TEXT_SCORE.as(randomAlphaUnderscore()),
    });
  }

  if (similarTo) {
    Object.assign(columns, {
      semanticScore:
        sql<number>`${cosineSimilarity(TextAnnotationTable.embedding, similarTo)}`.as(
          randomAlphaUnderscore(),
        ),
      semanticRank:
        sql<number>`ROW_NUMBER() OVER (ORDER BY ${cosineSimilarity(TextAnnotationTable.embedding, similarTo)} DESC)`.as(
          randomAlphaUnderscore(),
        ),
    });
  }

  return columns as unknown as DynamicResult<T, K, A>;
}

const ontologyMappingSubquery = BASE_ONTOLOGY_QUERY.where(undefined).as(
  randomAlphaUnderscore(),
);
type OntologyMappingColumns =
  (typeof ontologyMappingSubquery)["_"]["selectedFields"];
type OntologyMappingColumnNames = keyof OntologyMappingColumns;
type OntologyTablePickedColumns<K extends keyof OntologyMappingColumns> = {
  [P in K]: OntologyMappingColumns[P];
};

type WrapperResult<
  T extends ColumnOptions,
  K extends keyof TextAnnotationTableColumns = never,
  A extends Record<string, SQL.Aliased> = {},
  O extends keyof OntologyMappingColumns = never,
> = DynamicResult<T, K, A> & OntologyTablePickedColumns<O>;

function _getAnnotationsWithOntology<
  T extends ColumnOptions,
  A extends Record<string, SQL.Aliased> = {},
  K extends keyof TextAnnotationTableColumns = never,
  O extends keyof OntologyMappingColumns = never,
>({
  options,
  annotationFields,
  ontologyFields,
  limitTo,
  computedColumns,
}: {
  options: T;
  annotationFields?: K[];
  ontologyFields?: O[];
  computedColumns?: (mappingTable: OntologyMappingColumns) => A;
  limitTo?: string[];
}) {
  const ontologyMapping = OntologyMappings.getOntologyMappings(limitTo).as(
    randomAlphaUnderscore(),
  );

  const ontologyColumns: any = {};
  for (const f of ontologyFields ?? []) {
    ontologyColumns[f] =
      ontologyMapping["_"]["selectedFields"][f as OntologyMappingColumnNames];
  }

  const columns = {
    ..._getDefaultColumns({
      options,
      fields: annotationFields,
      computedColumns: computedColumns?.(
        ontologyMapping["_"]["selectedFields"],
      ),
    }),
    ...ontologyColumns,
  } as unknown as WrapperResult<T, K, A, O>;

  return db
    .select(columns)
    .from(TextAnnotationTable)
    .innerJoin(
      ontologyMapping,
      eq(TextAnnotationTable.mapping, ontologyMapping.mapping),
    );
}

const _getFullTextSearchSentences = (query: string) => {
  return db
    .select({
      ...getTableColumns(TextAnnotationTable),
      score: FULL_TEXT_SCORE.as("score"),
      rank: FULL_TEXT_SCORE.as("rank"),
    })
    .from(TextAnnotationTable)
    .where(
      and(
        eq(TextAnnotationTable.type, "sentence"),
        not(
          sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
        ),
        sql`${TextAnnotationTable.content}  &@~ ${query}`,
      ),
    );
};

const GET_SENTENCES = db
  .select({
    content: TextAnnotationTable.content,
    sentenceAid: TextAnnotationTable.sentenceAid,
    sentenceId: TextAnnotationTable.sentenceId,
    documentId: TextAnnotationTable.documentId,
    textId: TextAnnotationTable.textId,
    metadata: TextAnnotationTable.metadata,
    embedding: TextAnnotationTable.embedding,
  })
  .from(TextAnnotationTable)
  .where(
    and(
      eq(TextAnnotationTable.type, "sentence"),
      not(
        sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
      ),
    ),
  );

export const createPathWildcards = (values: string[]) => {
  return sql.join(
    values.flatMap((v) => [v, `${v}.*`]).map((v) => sql`${v}`),
    sql`, `,
  );
};

export const matchPath = (column: SQLWrapper, values: string[]) => {
  return sql`${column} ~ any(array[${createPathWildcards(values)}]::lquery[])`;
};

export const Annotations = {
  getColumns: _getDefaultColumns,
  getSentences: () => GET_SENTENCES,
  getFullTextSearchSentences: (query: string) =>
    _getFullTextSearchSentences(query),
  getAnnotationsWithOntology: _getAnnotationsWithOntology,
  getFullTextSnippet: function (query: string, text: SQLWrapper) {
    return sql<string>`array_to_string(pgroonga_snippet_html (${text},
    								 pgroonga_query_extract_keywords(${query})), '\n')`;
  },
  fullTextScore: FULL_TEXT_SCORE,
  fullTextRank: FULL_TEXT_RANK,
  eventArgs: EVENT_ARGS,
  getFullTextMatch: (query: string, text: SQLWrapper) =>
    sql`${text} &@~  (${query})`,
  getSemanticRank: (
    embedding1: CoalesceArgument<number[]>,
    embedding2: number[] | string[] | Column | SQL.Aliased<number[]>,
  ) =>
    sql<number>`DENSE_RANK() OVER (ORDER BY ${cosineSimilarity(embedding1, embedding2)} DESC)`,
  isSentence: eq(TextAnnotationTable.type, "sentence"),
  isNotSentence: ne(TextAnnotationTable.type, "sentence"),
  isNotStopword: not(
    sql<boolean>`COALESCE((${TextAnnotationTable.metadata}->>'is_stopword')::boolean,false)`,
  ),
} as const;

export const OntologyMappings = {
  getOntologyMappings: function (limitTo?: string[]) {
    return BASE_ONTOLOGY_QUERY.where(
      limitTo ? matchPath(OntologyTable.path, limitTo) : undefined,
    );
  },
};
