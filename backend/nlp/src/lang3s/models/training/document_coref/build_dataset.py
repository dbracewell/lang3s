import os
import re
from collections import defaultdict

import jsonlines
import pandas as pd
from lang3s_job_service import File
from tqdm import tqdm

from lang3s.models.coref_ranker import create_coref_mention
from lang3s.models.training.document_coref.coref_config import (
    GUM_DIR,
    SYNTHETIC_DATA,
    TRAINING_DATA_DIR,
    WIKICOREF_DIR,
)
from lang3s.models.training.document_coref.io import save_preprocessed_data
from lang3s.nlp.shared_types import Document, Metadata
from lang3s.pipeline import pipeline
from lang3s.pipeline.runner import pipeline_from_tokens

os.environ["TQDM_DISABLE"] = "0"


def parse_and_embed_synthetic_text(filepath):
    # Regex to find <m c="ID">text</m>
    pattern = re.compile(r'<m c="(?:COREF_)?(\d+)">(.+?)</m>')
    all_documents = []
    with jsonlines.open(filepath) as reader:
        for doc in reader:
            tagged_text = doc["generated_text"]
            clean_text = ""
            mentions = []
            mention_counter = 1
            current_idx = 0

            # 1. Parse the tags and calculate perfect character offsets
            for match in pattern.finditer(tagged_text):
                cluster_id = int(match.group(1))
                mention_text = match.group(2)

                # Add the raw text that came *before* the XML tag
                start_tag_idx = match.start()
                clean_text += tagged_text[current_idx:start_tag_idx]

                # Calculate where this entity starts and ends in our newly cleaned string
                char_start = len(clean_text)
                char_end = char_start + len(mention_text)

                # Append the actual entity text
                clean_text += mention_text

                mentions.append(
                    {
                        "id": mention_counter,
                        "text": mention_text,
                        "char_start": char_start,
                        "char_end": char_end,
                        "cluster_id": cluster_id,
                    }
                )
                mention_counter += 1
                current_idx = match.end()

            # Append any remaining text after the final XML tag
            clean_text += tagged_text[current_idx:]

            # 2. Run the clean text through spaCy to get your metadata
            files = [File(content=clean_text)]
            doc = pipeline(files, log=False)[0]
            formatted_document = []

            mention_span_set = set()
            for m in mentions:
                mention_span_set.add((m["char_start"], m["char_end"]))

            next_cluster_id = 100
            for token in doc.text.tokens:
                if token.value == "PRON":
                    start_char = token[Metadata.START_CHAR]
                    end_char = token[Metadata.END_CHAR]
                    if (start_char, end_char) not in mention_span_set:
                        mentions.append(
                            {
                                "id": mention_counter,
                                "text": token.text,
                                "char_start": start_char,
                                "char_end": end_char,
                                "cluster_id": next_cluster_id,
                            }
                        )
                        next_cluster_id += 1
                        mention_counter += 1

            for m in mentions:
                start_token = doc.text.get_token_for_char_offset(m["char_start"])
                end_token = doc.text.get_token_for_char_offset(m["char_end"] - 1)
                span = doc.text.create_span(
                    start=start_token.start,
                    end=end_token.end,
                    type="entity",
                    value="UNKNOWN",
                    source="generated",
                )

                if span.entities:
                    span = span.entities[0]
                elif len(span.tokens) == 1 and span.head.value == "PRON":
                    span = span.tokens[0]

                embedding = span.embedding
                # Re-use the exact robust function we built earlier!
                mention_doc = {
                    "id": m["id"],
                    "text": span.text,
                    "token_start": span.start,
                    "token_end": span.end,
                    "cluster_id": m["cluster_id"],
                    "emb": embedding,
                }
                mention_doc.update(create_coref_mention(span))
                formatted_document.append(mention_doc)

            all_documents.append(formatted_document)
            # return clean_text, formatted_document
    return all_documents


def parse_conll_coref(filepath):
    """
    Parses a CoNLL-formatted TSV coreference file into the training dictionary format.
    """
    documents = []
    document_tokens: list[list[str]] = []
    document_index = -1
    final_documents = []

    with open(filepath, "r", encoding="utf-8") as f:
        current_doc_mentions = []
        tokens = []
        open_mentions = defaultdict(list)
        mention_counter = 1

        for line in f:
            line = line.strip()

            # Document boundaries
            if line.startswith("#begin document") or line.startswith(
                "# begin document"
            ):
                current_doc_mentions = []
                tokens = []
                open_mentions.clear()
                mention_counter = 1
                document_index += 1
                document_tokens.append([])
                continue

            if line.startswith("#end document") or line.startswith("# end document"):
                for cid, stack in open_mentions.items():
                    if len(stack) > 0:
                        print(
                            f"⚠️ Warning: Cluster {cid} was opened but never closed in this document."
                        )
                # Sort mentions chronologically by their start index
                current_doc_mentions.sort(key=lambda x: x["token_start"])
                documents.append(current_doc_mentions)
                document_tokens[document_index] += tokens
                continue

            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            token_idx = len(tokens)

            if len(parts) >= 12:
                token_text = parts[3]
                coref_col = parts[-1]
            elif len(parts) == 3:
                token_text = parts[1]
                coref_col = parts[2]
            elif len(parts) > 3:
                token_text = parts[3]
                coref_col = "-"
            else:
                continue

            if token_text == "-LRB-":
                token_text = "("
            elif token_text == "-RRB-":
                token_text = ")"
            elif token_text == "-LSB-":
                token_text = "["
            elif token_text == "-RSB-":
                token_text = "]"
            elif token_text == "-LCB-":
                token_text = "("
            elif token_text == "-RCB-":
                token_text = "["
            elif token_text == "``" or token_text == "''":
                token_text = '"'

            token_text = token_text.strip()
            tokens.append(token_text)

            # Parse the coreference column
            if coref_col != "-":
                for match in re.finditer(r"(\()?(\d+)(\))?", coref_col):
                    has_open = match.group(1) == "("
                    cluster_id = int(match.group(2))
                    has_close = match.group(3) == ")"

                    if has_open and has_close:
                        # Single-token mention (e.g., "(5)")
                        current_doc_mentions.append(
                            {
                                "id": mention_counter,
                                "text": token_text,
                                "token_start": token_idx,
                                "token_end": token_idx,
                                "cluster_id": cluster_id,
                            }
                        )
                        mention_counter += 1

                    elif has_open:
                        # Start of a multi-token mention (e.g., "(5")
                        open_mentions[cluster_id].append(token_idx)

                    elif has_close:
                        # End of a multi-token mention (e.g., "5)")
                        if (
                            cluster_id not in open_mentions
                            or len(open_mentions[cluster_id]) == 0
                        ):
                            print(
                                f"⚠️ Warning: Unmatched closing bracket for cluster {cluster_id} at token '{token_text}'. Skipping."
                            )
                            continue

                        start_idx = open_mentions[cluster_id].pop()
                        span_text = " ".join(tokens[start_idx : token_idx + 1])

                        current_doc_mentions.append(
                            {
                                "id": mention_counter,
                                "text": span_text,
                                "token_start": start_idx,
                                "token_end": token_idx,
                                "cluster_id": cluster_id,
                            }
                        )
                        mention_counter += 1

        for doc, tokens in zip(documents, document_tokens):
            lang3s_doc = pipeline_from_tokens(
                [tokens],
                language="en",
                log=False,
                tasks=set(),
            )[0]
            output_document = []

            mention_span_set = set()
            for mention in doc:
                mention_span_set.add((mention["token_start"], mention["token_end"]))

            next_cluster_id = max(mention["cluster_id"] for mention in doc) + 1
            next_mention_id = max(mention["id"] for mention in doc) + 1
            for token in lang3s_doc.text.tokens:
                if token.value == "PRON":
                    if (token.start, token.end) not in mention_span_set:
                        doc.append(
                            {
                                "id": next_mention_id,
                                "text": token.text,
                                "token_start": token.start,
                                "token_end": token.end,
                                "cluster_id": next_cluster_id,
                            }
                        )
                        next_cluster_id += 1
                        mention_counter += 1

            for mention in doc:
                start_token = lang3s_doc.text.tokens[mention["token_start"]]
                end_token = lang3s_doc.text.tokens[mention["token_end"]]
                span = lang3s_doc.text.create_span(
                    start_token.start,
                    end_token.end,
                    source="conll",
                    type="token",
                    value="PRON",
                )

                if span.entities:
                    span = span.entities[0]
                mention.update(create_coref_mention(span))
                output_document.append(mention)
            final_documents.append(output_document)

    return final_documents


def process_gap_dataset(split="train"):
    urls = {
        "train": "https://raw.githubusercontent.com/google-research-datasets/gap-coreference/master/gap-development.tsv",
        "validation": "https://raw.githubusercontent.com/google-research-datasets/gap-coreference/master/gap-validation.tsv",
        "test": "https://raw.githubusercontent.com/google-research-datasets/gap-coreference/master/gap-test.tsv",
    }

    df = pd.read_csv(urls[split], sep="\t")
    formatted_documents = []
    files = [File(content=row["Text"]) for _, row in df.iterrows()]
    docs = pipeline(files, log=False, disable_ner=True)
    doc: Document
    for (_, row), doc in tqdm(zip(df.iterrows(), docs)):
        mentions_raw = [
            {"type": "A", "text": row["A"], "offset": row["A-offset"]},
            {"type": "B", "text": row["B"], "offset": row["B-offset"]},
            {
                "type": "Pronoun",
                "text": row["Pronoun"],
                "offset": row["Pronoun-offset"],
            },
        ]

        # Sort mentions strictly by their character offset (chronological order)
        mentions_raw.sort(key=lambda x: x["offset"])

        # Determine clustering based on GAP's boolean labels
        # GAP only tests the pronoun against A and B.
        # We assign base cluster IDs, and merge them if the label is True.
        cluster_map = {
            "A": 1,  # Entity A is cluster 1
            "B": 2,  # Entity B is cluster 2
            "Pronoun": 3,  # Defaults to cluster 3 (no coref)
        }

        if row["A-coref"]:
            cluster_map["Pronoun"] = 1  # Pronoun merges into Entity A's cluster
        elif row["B-coref"]:
            cluster_map["Pronoun"] = 2  # Pronoun merges into Entity B's cluster

        # Build the final document list
        doc_mentions = []
        for i, m in enumerate(mentions_raw):
            start_token = doc.text.get_token_for_char_offset(m["offset"])
            end_token = doc.text.get_token_for_char_offset(
                m["offset"] + len(m["text"]) - 1
            )
            span = doc.text.create_span(
                start_token.start,
                end_token.end,
                "dummy",
                "token",
                "PRON",
            )
            entity = span.entities[0] if span.entities else None
            if entity:
                mention = create_coref_mention(entity)
            else:
                mention = create_coref_mention(span)
            mention_info = {
                "id": i + 1,
                "text": m["text"],
                "cluster_id": cluster_map[m["type"]],
            }
            mention_info.update(mention)
            doc_mentions.append(mention_info)

        formatted_documents.append(doc_mentions)

    return formatted_documents


if __name__ == "__main__":
    training_data = []

    training_data += parse_and_embed_synthetic_text(SYNTHETIC_DATA)
    training_data += process_gap_dataset()

    conll_files = [
        os.path.join(WIKICOREF_DIR, file)
        for file in os.listdir(WIKICOREF_DIR)
        if file.endswith("conll")
    ]
    conll_files += [
        os.path.join(GUM_DIR, file)
        for file in os.listdir(GUM_DIR)
        if file.endswith(".conll")
    ]

    for file in tqdm(conll_files):
        training_data.extend(parse_conll_coref(file))

    save_preprocessed_data(
        documents=training_data,
        filepath=TRAINING_DATA_DIR,
    )
