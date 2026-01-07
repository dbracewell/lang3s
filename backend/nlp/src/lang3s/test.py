import math
import statistics
import string
from collections import Counter, defaultdict
from typing import Annotated

import jsonlines
import networkx as nx
import numpy as np
from lang3s_job_service import File
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity

from lang3s import config
from lang3s.agent.llm import tool
from lang3s.app import Application
from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import TextDatabase
from lang3s.nlp.keyword_extraction import extract_keywords
from lang3s.pipeline import pipeline
from lang3s.shared_types import Text


@tool(name="get_weather", description="Gets the weather for a given location")
def get_weather(location: Annotated[str, "The location to retrieve weather for"]):
    return "76"


class TextRankNGram:
    def __init__(self, text: Text, n=1, window_size=3, lang="english"):
        """
        Initializes the TextRank algorithm.

        Args:
            text (str): The input text.
            n (int): The length of n-grams to rank (1=words, 2=bigrams, etc.).
            window_size (int): The co-occurrence window size.
            lang (str): Language for stopwords.
        """
        self.text = text
        self.n = n
        self.window_size = window_size
        self.lang = lang
        self.graph = nx.Graph()
        self.ranked_ngrams = []

    def _preprocess(self):
        """Tokenizes, lowers, and removes stopwords/punctuation."""
        # Tokenize and lower
        tokens = self.text.tokens

        # Filter: Alphanumeric only + remove stopwords
        # Note: For N>1, you might sometimes want to keep stopwords in the middle
        # (e.g. "state of the art"), but strictly filtering is standard for keyword extraction.
        filtered_tokens = [
            word.lemma.lower()
            for word in tokens
            if not word.is_stopword
            and not word.entities
            and (word.value == "NOUN" or word.value == "ADJ" or word.value == "PROPN")
            and word.lemma.isalnum()
        ]
        return filtered_tokens

    def _get_ngrams(self, tokens):
        """Generates a list of n-grams from the token list."""
        if self.n == 1:
            return tokens

        # Zip the list against itself shifted by 1..n to create tuples
        # Example for n=2: zip([a,b,c], [b,c,d]) -> (a,b), (b,c)
        return list(zip(*[tokens[i:] for i in range(self.n)]))

    def analyze(self):
        """Executes the TextRank algorithm."""
        tokens = self._preprocess()

        # 1. Generate N-grams (Nodes)
        ngrams_list = self._get_ngrams(tokens)

        if not ngrams_list:
            return []

        # 2. Build the Graph
        # We iterate through the ngrams list and connect items within the window
        for i, ngram in enumerate(ngrams_list):
            # Add node (if not exists)
            if not self.graph.has_node(ngram):
                self.graph.add_node(ngram)

            # Look ahead in the window to establish connections
            # The window defines how far neighbors can be to be considered "related"
            window_end = min(len(ngrams_list), i + self.window_size)

            for j in range(i + 1, window_end):
                neighbor = ngrams_list[j]

                # Weighted Graph: Increment weight if edge exists
                if self.graph.has_edge(ngram, neighbor):
                    self.graph[ngram][neighbor]["weight"] += 1
                else:
                    self.graph.add_edge(ngram, neighbor, weight=1)

        # 3. Run PageRank
        # We use undirected graph, weighted edges
        scores = nx.pagerank(self.graph, weight="weight")

        # 4. Sort and Format
        # Sort by score descending
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

        # Flatten tuple n-grams back to strings for display
        self.ranked_ngrams = [
            (" ".join(gram) if isinstance(gram, tuple) else gram, score)
            for gram, score in sorted_scores
        ]

        return self.ranked_ngrams

    def get_top_n(self, limit=5):
        """Returns the top N results."""
        return self.ranked_ngrams[:limit]


class YakeExtractor:
    def __init__(self, text: Text, n=3, dedup_lim=0.9, lang="english", window=1):
        """
        Args:
            text (str): Input text.
            n (int): Max N-gram size.
            dedup_lim (float): Threshold to remove duplicate keywords (0.9 = strict).
            window (int): Window size for context relatedness.
        """
        self.text = text
        self.n = n
        self.dedup_lim = dedup_lim
        self.punctuation = string.punctuation
        self.stopwords = set([t.text.lower() for t in text.tokens if t.is_stopword])
        self.window = window

    def _preprocess(self):
        """Splits text into sentences and tokens."""
        sentences = [s for s in self.text.sentences]
        tokens = [s.tokens for s in self.text.sentences]
        # Flatten for word stats
        all_tokens = [w for s in tokens for w in s]
        return sentences, tokens, all_tokens

    def _calculate_word_scores(self, all_tokens, sentences):
        """
        Calculates the 5 separate features for every unique word.
        Returns a dictionary: {word: combined_score}
        """
        # Basic Stats
        freq_counter = Counter(t.text.lower() for t in all_tokens)
        distinct_words = set(freq_counter.keys())
        total_tokens = len(all_tokens)

        # 1. Casing (W_case)
        # Ratio of times word is uppercase vs total times
        casing_counts = defaultdict(int)
        for t in all_tokens:
            if t.text[0].isupper():
                casing_counts[t.text.lower()] += 1

        w_case = {}
        for w in distinct_words:
            # We favor capitalized words (lower score is better in YAKE)
            # Logic: Max(TF_upper, TF_lower) / log(TF_total)
            w_case[w] = max(casing_counts[w], freq_counter[w] - casing_counts[w])
            w_case[w] /= math.log(freq_counter[w]) + 1  # smooth

        # 2. Position (W_pos)
        # Median position of the word in the text
        w_pos = {}
        positions = defaultdict(list)
        for i, t in enumerate(all_tokens):
            positions[t.text.lower()].append(i)

        for w in distinct_words:
            median_pos = statistics.median(positions[w])
            # Normalize: closer to 0 is better.
            # Original paper uses complex log smoothing, simplified here:
            w_pos[w] = math.log(math.log(median_pos + 3) + 1)

        # 3. Frequency (W_freq)
        # Freq / (Mean + StdDev)
        frequencies = list(freq_counter.values())
        mean_freq = statistics.mean(frequencies)
        std_freq = statistics.stdev(frequencies) if len(frequencies) > 1 else 0

        w_freq = {}
        for w in distinct_words:
            w_freq[w] = freq_counter[w] / (mean_freq + std_freq + 1)

        # 4. Relatedness (W_rel) - Context Dispersion
        # (Distinct words to left + distinct words to right) / TF
        # Using a simplified co-occurrence check
        w_rel = {}
        # This part can be slow, so we approximate or skip for simple implementations
        # Setting to 1.0 (neutral) for this lightweight version to save compute
        for w in distinct_words:
            w_rel[w] = 1.0

            # 5. Sentence (W_sent)
        # Frequency of sentences containing the word / Total sentences
        w_sent = {}
        for w in distinct_words:
            count = sum(
                1
                for s in sentences
                if any(x.lower() == w for x in [t.text for t in s.tokens])
            )
            w_sent[w] = count / len(sentences)

        # Combine Features -> S(w)
        # YAKE Formula: Product of features / denominators
        # Simplified aggregation ensuring "Lower is Better"
        final_scores = {}
        for w in distinct_words:
            # Skip pure punctuation
            if w in self.punctuation:
                final_scores[w] = 100.0  # High score = bad
                continue

            # Weighted formula
            # Note: The exact official weights are heuristic.
            # We invert Frequency/Sentence features because usually High Freq = Good,
            # but in YAKE output, Low Score = Good.

            # If word is stop word, penalize heavily
            stop_penalty = 10.0 if w in self.stopwords else 1.0

            s_a = w_case[w]
            s_b = w_pos[w]
            s_c = 1.0 / (w_freq[w] + 1)  # Invert freq
            s_d = w_rel[w]
            s_e = 1.0 / (w_sent[w] + 1)  # Invert sent freq

            score = (s_a * s_b * s_c * s_d * s_e) * stop_penalty
            final_scores[w] = score

        return final_scores

    def _generate_candidate_keywords(self, sentences, word_scores):
        """
        Generates N-grams and scores them.
        S(kw) = Product(S(w)) / (Sum(S(w)) + 1) * StopwordPenalty
        """
        candidates = {}

        for sentence_tokens in sentences:
            # Tokenize and lower
            tokens = [t.text.lower() for t in sentence_tokens]

            # Sliding window 1..N
            for n_gram_len in range(1, self.n + 1):
                for i in range(len(tokens) - n_gram_len + 1):
                    window = tokens[i : i + n_gram_len]

                    # Heuristics:
                    # 1. Don't start/end with stopword (unless n=1)
                    if n_gram_len > 1:
                        if window[0] in self.stopwords or window[-1] in self.stopwords:
                            continue

                    # 2. Must contain alphanumeric
                    if not any(w.isalnum() for w in window):
                        continue

                    phrase = " ".join(window)

                    # Calculate Phrase Score
                    # Formula: Prod(Score(w)) / (Sum(Score(w)) + 1)
                    product_score = 1.0
                    sum_score = 0.0

                    for w in window:
                        s = word_scores.get(w, 1.0)
                        product_score *= s
                        sum_score += s

                    final_score = product_score / (sum_score + 1)

                    # Penalize short words slightly to favor descriptive phrases
                    if n_gram_len == 1 and len(window[0]) < 3:
                        final_score *= 2.0

                    candidates[phrase] = final_score

        return candidates

    def _deduplicate(self, candidates):
        """
        Removes similar keywords (e.g. 'learning' if 'machine learning' exists and has better score).
        """
        # Sort by score (asc)
        sorted_candidates = sorted(candidates.items(), key=lambda x: x[1])
        final_list = []

        for phrase, score in sorted_candidates:
            is_dup = False
            for keep_phrase, keep_score in final_list:
                # Simple containment check + ratio
                # If "learning" is in "machine learning", and the scores are close, drop "learning"
                if phrase in keep_phrase and score > keep_score:
                    is_dup = True
                    break
                # Levenshtein could go here for fuzziness

            if not is_dup:
                final_list.append((phrase, score))

        return final_list

    def extract(self, limit=10):
        sentences_raw, tokens_nested, all_tokens = self._preprocess()
        word_scores = self._calculate_word_scores(all_tokens, sentences_raw)
        candidates = self._generate_candidate_keywords(tokens_nested, word_scores)

        # Deduplicate and sort
        results = self._deduplicate(candidates)
        return results[:limit]


class Sentence(BaseModel):
    sentence: str


def rake(doc: Text):
    spans = []
    for sentence in doc.sentences:
        buffer = []
        for token in sentence.tokens:
            if not token.is_stopword:
                buffer.append(token.lemma.lower())
                if len(buffer) >= 3:
                    spans.append(list(buffer))
                    buffer.clear()
            elif len(buffer) > 0:
                spans.append(list(buffer))
                buffer.clear()
        if len(buffer) > 0:
            spans.append(list(buffer))

    word_freq = Counter()
    word_degree = defaultdict(int)
    for span in spans:
        for word in span:
            word_freq[word] += 1
            word_degree[word] += len(span)

    word_scores = {}
    for word, freq in word_freq.items():
        word_scores[word] = word_degree[word] / freq

    phrase_scores = Counter()
    for span in spans:
        score = 0
        for word in span:
            score += word_scores.get(word, 0)
        phrase_scores[" ".join(span)] = score

    return sorted(phrase_scores.items(), key=lambda x: x[1], reverse=True)[:5]


def mmr_rank(doc_embedding, candidate_embeddings, candidates, top_n=5, diversity=0.7):
    """
    Selects keywords using Maximal Marginal Relevance.

    Args:
        doc_embedding (np.array): The embedding of the full document (1, dim).
        candidate_embeddings (np.array): Embeddings of all candidate keywords (N, dim).
        candidates (list): List of candidate strings.
        top_n (int): Number of keywords to extract.
        diversity (float): 0.0 (minimal diversity) to 1.0 (max diversity).
    """

    # Calculate similarity of all candidates to the document
    # (These are the 'relevance' scores)
    candidate_similarity = cosine_similarity(candidate_embeddings, doc_embedding)
    candidate_similarity = candidate_similarity.reshape(-1, 1)
    weighting = np.linspace(0, 0.2, 5)
    weights = np.array([weighting[min(len(c.split()), 5)] for c in candidates]).reshape(
        -1, 1
    )
    candidate_similarity += weights
    # Indices of candidates selected so far
    keywords_idx = [np.argmax(candidate_similarity).item()]
    candidates_idx = [i for i in range(len(candidates)) if i != keywords_idx[0]]

    for _ in range(top_n - 1):
        # 1. Get relevance of remaining candidates to the document
        candidate_similarities = candidate_similarity[candidates_idx, :]

        # 2. Get similarity of remaining candidates to ALREADY selected keywords
        # Result shape: (remaining_candidates, selected_keywords)
        target_similarities = cosine_similarity(
            candidate_embeddings[candidates_idx], candidate_embeddings[keywords_idx]
        )
        target_similarities = target_similarities.reshape(
            len(candidates_idx), len(keywords_idx)
        )
        # 3. Calculate MMR score
        # We take the max similarity to any selected keyword (redundancy penalty)
        mmr_score = (
            1 - diversity
        ) * candidate_similarities - diversity * target_similarities.max(
            axis=1
        ).reshape(-1, 1)

        # 4. Pick the candidate with the highest MMR score
        mmr_idx = candidates_idx[np.argmax(mmr_score)]

        keywords_idx.append(mmr_idx)
        candidates_idx.remove(mmr_idx)

    return [(candidates[idx], candidate_similarity[idx][0]) for idx in keywords_idx]


def cos(e1, e2):
    return np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))


class Test(Application):
    def run(self):
        # client = TopicModelClient()

        textdb = TextDatabase()
        client = TopicModelClient()
        batch = 100
        total_docs = textdb.doc_count
        for i in range(0, total_docs, batch):
            print("PROCESSING BATCH ", (i + 1))
            client.partial_fit([doc for doc in textdb.get_documents(i, batch)])

        client.finalize()
        exit()
        config.USE_COREFERENCE = False
        with jsonlines.open("/Users/ik/prj/Lang3s/news.jsonl") as reader:
            files = [File.model_validate(d) for d in reader]
        docs = pipeline(files[:500], tasks=set())

        clusters = []
        cluster_centroids = []

        for doc in docs:
            keywords = extract_keywords(doc.text, top_n=10)
            for term, sim, embedding in keywords:
                if not clusters:
                    clusters.append([term])
                    cluster_centroids.append(embedding)
                else:
                    similarities = [cos(embedding, c) for c in cluster_centroids]
                    max_arg = np.argmax(similarities)
                    max_sim = similarities[max_arg]
                    if max_sim >= 0.65:
                        weight = len(clusters[max_arg])
                        clusters[max_arg].append(term)
                        cluster_centroids[max_arg] = (
                            ((weight * cluster_centroids[max_arg]) + embedding)
                            / (weight + 1)
                        ).squeeze()
                    else:
                        clusters.append([term])
                        cluster_centroids.append(embedding)

        merged = []
        merged_centroids = []
        added = set()
        for i in range(len(clusters)):
            if i in added:
                continue
            ci = clusters[i]
            cie = cluster_centroids[i]
            for j in range(i + 1, len(clusters)):
                cj = clusters[j]
                cje = cluster_centroids[j]
                if cos(cie, cje) >= 0.65:
                    ci.extend(cj)
                    wie = len(ci)
                    wje = len(cj)
                    cie = (wie * cie + wje * cje) / (wie + wje)
                    added.add(j)
            merged_centroids.append(cie)
            merged.append(ci)

        cluster_centroids = merged_centroids
        clusters = merged

        for c in clusters:
            print(c)

        # cnts = Counter()
        # for doc in docs:
        #     pprint(doc.text.text)
        #     kw = rake(doc.text)
        #     print(kw)
        #     tr = TextRankNGram(doc.text, n=2)
        #     kw = tr.analyze()[:5]
        #     print(kw)
        #     yake = YakeExtractor(doc.text)
        #     kw = yake.extract(5)
        #     print(kw)
        #
        #     candidates = []
        #     candidate_embeddings = []
        #     for sentence in doc.text.sentences:
        #         buffer_text = []
        #         buffer_embedding = []
        #         buffer_pos = []
        #         for token in sentence.tokens:
        #             if (
        #                 token.value == "NOUN" or token.value == "ADJ"
        #             ) and not token.is_stopword:
        #                 buffer_pos.append(token.value)
        #                 buffer_text.append(token.lemma.lower())
        #                 buffer_embedding.append(token.embedding)
        #             elif len(buffer_text) > 0:
        #                 if "NOUN" in buffer_pos:
        #                     candidates.append(" ".join(buffer_text))
        #                     candidate_embeddings.append(
        #                         np.sum(buffer_embedding, axis=0) / len(buffer_embedding)
        #                     )
        #                 buffer_text = []
        #                 buffer_embedding = []
        #                 buffer_pos = []
        #         if len(buffer_text) > 0 and "NOUN" in buffer_pos:
        #             candidates.append(" ".join(buffer_text))
        #             candidate_embeddings.append(
        #                 np.sum(buffer_embedding, axis=0) / len(buffer_embedding)
        #             )
        #
        #     final_candidates = []
        #     final_candidate_embeddings = []
        #     for idx, (c, e) in enumerate(zip(candidates, candidate_embeddings)):
        #         if len(c.split()) > 1:
        #             final_candidates.append(c)
        #             final_candidate_embeddings.append(e)
        #         else:
        #             add = True
        #             for c2 in candidates[idx + 1 :]:
        #                 if len(c2.split()) == 1:
        #                     continue
        #                 if c in c2.split():
        #                     add = False
        #                     break
        #             if add:
        #                 final_candidates.append(c)
        #                 final_candidate_embeddings.append(e)
        #
        #     kw = mmr_rank(
        #         doc.text.embedding.reshape(1, -1),
        #         np.stack(final_candidate_embeddings),
        #         final_candidates,
        #         top_n=5,
        #         diversity=0.5,
        #     )
        #     # kw = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        #     print(kw)
        #     print()
        #     # cnts.update({k: 1 for k, v in kw})

        # print(cnts)


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
