import json
from collections import defaultdict
from time import perf_counter, time

import duckdb
import numpy as np
from psycopg import sql
from sklearn.cluster import HDBSCAN
from sqlalchemy import select
from tqdm import tqdm
from umap import UMAP

from lang3s.app import Application
from lang3s.data.db import Database
from lang3s.data.db.models import TextAnnotationsTable
from lang3s.data.io.serialization import deserialize
from lang3s.maths import cosine


class Test(Application):
    def run(self):
        conn = duckdb.connect("/Users/ik/prj/Lang3s/file.db")

        # conn.execute("INSTALL postgres;")
        # conn.execute("LOAD postgres;")
        # conn.execute(
        #     "ATTACH 'dbname=lang3s user=admin password=abba host=192.168.0.100' AS pg (TYPE postgres)"
        # )
        # conn.execute(
        #     "CREATE TABLE text_annotations AS SELECT * FROM pg.public.text_annotations;"
        # )
        # conn.execute("""
        #              CREATE OR REPLACE VIEW annotation_norm as
        #              select UPPER(COALESCE(metadata->>'coref_text',text)) as text,
        #                     type,
        #                     value,
        #                     COUNT(DISTINCT doc_id) as document_count,
        #                     COUNT(DISTINCT sentence_id) as sentence_count,
        #                     COUNT(0) as mention_count
        #              FROM text_annotations
        #              GROUP BY metadata, UPPER(COALESCE(metadata->>'coref_text',text)) , type, value
        #             """)

        start = time()
        r = conn.query(
            """SELECT id, text
               FROM text_annotations
               WHERE text ilike '%wall%street%'
               """
        )
        for row in r.fetchall():
            print(row)
        end = time()
        print(end - start)
        exit()
        conn.sql(
            "CREATE TABLE IF NOT EXISTS ANNOTATIONS (id TEXT PRIMARY KEY, type TEXT, value TEXT, text TEXT, embedding FLOAT[384])"
        )
        db = Database()
        with db.session() as session:
            stmt = select(TextAnnotationsTable).execution_options(yield_per=100)
            i = 0
            for row in tqdm(session.scalars(stmt)):
                conn.execute(
                    f"INSERT INTO ANNOTATIONS VALUES (?,?,?,?,?)",
                    [
                        row.id,
                        row.type_,
                        row.value,
                        row.content,
                        row.embedding.to_numpy(),
                    ],
                )
                i += 1
                if i % 100 == 0:
                    conn.commit()

        conn.close()
        exit()
        # with open(
        #     "/Users/ik/prj/Lang3s/backend/nlp/src/lang3s/reddit_style_corpus.json"
        # ) as fp:
        #     documents = json.load(fp)
        #     files = [
        #         File(
        #             content=doc["text"],
        #             docId=doc["id"],
        #             metadata={"source": doc["source"]},
        #         )
        #         for doc in documents
        #     ]
        # config.USE_COREFERENCE = False
        # docs = pipeline(files)
        # serialize(docs, "/Users/ik/prj/Lang3s/reddit.docs")

        group_one = []
        group_two = []
        for doc in deserialize("/Users/ik/prj/Lang3s/reddit.docs"):
            if doc["source"] == "r/GenX":
                group_one.extend([s.tokens for s in doc.text.sentences])
            else:
                group_two.extend([s.tokens for s in doc.text.sentences])

        print(len(group_one), len(group_two))

        words = []
        embeddings = []
        for sentence in group_two:
            for word in sentence:
                words.append(word.text)
                embeddings.append(word.embedding)

        umap = UMAP(n_components=20, init="random", n_jobs=10)
        embeddings = umap.fit_transform(embeddings)
        clusterer = HDBSCAN(min_cluster_size=3, min_samples=1, n_jobs=10)
        clusters = clusterer.fit_predict(embeddings)
        cluster_words = defaultdict(list)

        for text, cluster in zip(words, clusters):
            if cluster == -1:
                continue
            cluster_words[cluster].append(text)

        for cluster, words in cluster_words.items():
            print(f"Cluster {cluster}: {words}")

        exit(0)

        genx_words = defaultdict(list)
        millennial_words = defaultdict(list)

        # Universal POS tags: NOUN, VERB, ADJ, ADV, PROPN are content words
        valid_pos = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}

        for sentence in group_one:
            for token in sentence:
                genx_words[token.text.lower()].append(token.embedding)

        for sentence in group_two:
            for token in sentence:
                millennial_words[token.text.lower()].append(token.embedding)

        results = []
        min_count = 5

        for word, embeddings in genx_words.items():
            if (
                word in millennial_words
                and len(embeddings) >= min_count
                and len(millennial_words[word]) >= min_count
            ):
                genx_vec = np.mean(embeddings, axis=0)
                mill_vec = np.mean(millennial_words[word], axis=0)
                score = cosine(genx_vec, mill_vec)
                results.append((word, score))

        results.sort(key=lambda x: x[1])

        print("Top words used differently (GenX vs Millennials):")
        for word, score in results[:50]:
            print(f"{word}: {score:.4f}")

        exit()
        db = Database()
        with db.cursor() as cursor:
            sql_query = sql.SQL("""
                                SELECT keyword,embedding
                                FROM keywords
                                """)
            cursor.execute(sql_query)
            results = cursor.fetchall()

        keywords = [r[0] for r in results]
        embeddings = [r[1].to_numpy() for r in results]

        umap_2d = umap.UMAP(n_components=20, init="random", n_jobs=10)
        embeddings = umap_2d.fit_transform(embeddings)

        dbscan = HDBSCAN(min_cluster_size=20, min_samples=1, n_jobs=10)
        clusters = dbscan.fit_predict(embeddings)

        cluster_words = defaultdict(list)
        for text, cluster in zip(keywords, clusters):
            if cluster == -1:
                continue
            cluster_words[cluster].append(text)

        for cid, kw in cluster_words.items():
            print(kw[:10])

        # text = []
        # embeddings = []
        # for doc in docs:
        #     for chunk in doc.text.annotations_of_type("phrase_chunk"):
        #         if not chunk.is_stopword and chunk.value in ["NP", "ADJP"]:
        #             text.append(chunk.lemma)
        #             embeddings.append(chunk.embedding.tolist())
        # with open("embeddings.json", "w") as fp:
        #     json.dump(
        #         {
        #             "text": text,
        #             "embeddings": embeddings,
        #         },
        #         fp,
        #     )
        exit(0)
        with open("embeddings.json") as f:
            doc = json.load(f)
            text = doc["text"]
            embeddings = doc["embeddings"]

        embeddings = np.array(embeddings)
        print(embeddings.shape)
        # for embedding in embeddings:
        #     print(embedding.shape)

        umap_2d = umap.UMAP(n_components=20, init="random", n_jobs=10)
        embeddings = umap_2d.fit_transform(embeddings)

        hdbscan = HDBSCAN(min_cluster_size=5, min_samples=1, n_jobs=10)
        clusters = hdbscan.fit_predict(embeddings)
        cluster_words = defaultdict(list)
        for text, cluster in zip(text, clusters):
            if cluster == -1:
                continue
            cluster_words[cluster].append(text)

        for cluster, words in cluster_words.items():
            print(f"Cluster {cluster}: {words}")
            print()


#         from transformers import AutoTokenizer, AutoModelForCausalLM
#         import outlines
#
#         tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-4b-Instruct-2507")
#         model = outlines.from_transformers(
#             AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-4b-Instruct-2507").to("mps"),
#             tokenizer_or_processor=tokenizer)
#         #
#         # messages = [
#         #     {"role": "user", "content": "Give me an example sentence with Peter as the character."},
#         # ]
#         # inputs = tokenizer.apply_chat_template(
#         #     messages,
#         #     add_generation_prompt=True,
#         #     tools=[get_weather.tool.schema],
#         #     tokenize=True,
#         #     return_dict=True,
#         #     return_tensors="pt",
#         # ).to("mps")
#
#         chat = Chat()
#         chat.add_user_message("""
#         Given the following set of keywords and example sentences, generate a short (maximum 1 sentence)
#         name for the topic covered by the keywords and example sentences. The topic should be too generic or too
#         specific, but adequately describe the content. Please give the output as "name" or "netflix" like category.
#         Keywords: yukos, russian, rosneft, gazprom, russia
#         Example Sentences:
#         The Kremlin last year seized and sold Yukos' main production arm, Yugansk, to state-run oil group Rosneft for $9.3bn to offset a massive back tax bill.
# It has claimed that Russia imposed the huge tax bill and forced the sale of Yugansk as part of a campaign to destroy Yukos and its former owner Mihkail Khodorkovsky, who is facing a 10-year prison term in Russia for fraud and tax evasion.
# State-owned Rosneft bought the Yugansk unit for $9.3bn in a sale forced by Russia to part settle a $27.5bn tax claim against Yukos.
# Russian prosecutors are forcing the sale of the firm's most lucrative asset Yuganskneftegas to help pay a $27bn (£14bn) back tax bill, which they claim is owed by Yukos.
# By selling the Yukos unit to little-known Baikal and then to Rosneft, Russia is able to circumvent a host of tricky legal landmines, analysts said.
# Mr Khodorkovsky, who had funded liberal opposition groups, was arrested in October last year on fraud and tax evasion charges and is still in jail Analysts believe that if its production unit is auctioned off, it is likely to be bought up by a government-backed firm, like Gazprom, effectively bringing a large chunk of Russia's lucrative oil and gas industry back under state control.
# Yukos is currently suing four companies - Gazprom, its unit Gazpromneft, Rosneft and the shell company which won the bidding - for their part in Yugansk's disposal.
# The Russian government's argument for selling Yuganskneftegaz - the unit's full name - was that Yukos owed more than $27bn in back taxes for the years from 2000 onwards.
# The Russian government put Yukos's Yuganskneftegas subsidiary up for sale last week after hitting the company with a $27bn (£14bn) bill for back taxes and fines.
# The company is also seeking $20bn in a separate US lawsuit against Rosneft and Gazprom for their role in the sale of Yugansk.
# The Russian government forced the sale of Yukos' most lucrative asset as part of its action to enforce a $27bn back tax bill it says the company owes.
# Speaking on Tuesday, President Putin said Baikal was owned by individual investors who planned to build relationships with other Russian energy firms interested in the development of Yuganskneftegas.
# It had agreed to loan to an arm of Russian state gas firm Gazprom the money to bid for Yuganskneftegaz, as the Yukos unit is formally known.
# Speaking on NTV television, which is controlled by Gazprom, Mr Miller added that Yugansk, which was swallowed up by Rosneft late last year, will operate as a separate, state-owned oil firm headed by current Rosneft chief Sergei Bogdanchikov.
# Mystery surrounds new Yukos owner The fate of Russia's Yuganskneftegas - the oil firm sold to a little-known buyer on Sunday - is the subject of frantic speculation in Moscow.
# "Clearly the Chinese are trying to get some leverage [in Russia]," said Dmitry Lukashov, an analyst at brokerage Aton.
# The merger, backed by Russian authorities, will allow foreigners to trade in Gazprom shares.
# Rosneft, meanwhile, has agreed to merge with Gazprom, bringing a large chunk of Russia's very profitable oil business back under state control.
# Rosneft, meanwhile, has agreed to merge with Gazprom, bringing a large chunk of Russia's very profitable oil business back under state control.
# Russian newspapers have claimed that Baikal - which bought the Yuganskneftegas production unit for $9.4bn (261bn roubles, £4.8bn) on Sunday at a state provoked auction - has strong links with Surgutneftegas, Russia's fourth-biggest oil producer.
#         """)
#         outputs = model(chat,
#                         max_new_tokens=200)
#         print(outputs)
#         # print(get_weather.tool.arg_validator.model_validate_json(outputs))
#         # print(tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True))


if __name__ == "__main__":
    Test.from_cli().run_with_plugins()
