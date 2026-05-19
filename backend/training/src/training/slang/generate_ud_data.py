import json
from collections import Counter, defaultdict

import pandas as pd
import spacy
from tqdm import tqdm

from lang3s.data.filestore import FILE_STORE

INPUT_JSON = "/Users/ik/Downloads/data/words.json"  # Path to your downloaded CSV
OUTPUT_JSON = FILE_STORE.get_file_path("slang_vocab.json")
MIN_VOTES = 100
BATCH_SIZE = 1000


def process_urban_dict():
    nlp = spacy.load("en_core_web_lg", disable=["ner", "parser"])

    print("1. Loading JSON (this may take a moment)...")
    df = pd.read_json(INPUT_JSON, lines=True)  # type: ignore

    print("2. Filtering data...")
    df = df.dropna(subset=["word", "example"])

    # Keeping phrases with fewer than 5 spaces (approx 5-6 words max)
    df = df[df["word"].str.count(" ") < 5]

    # Filter by length or characters to remove garbage
    df = df[df["word"].str.len() > 1]

    # Keep only highly voted phrases
    df = df[df["thumbs_up"] > MIN_VOTES]

    # Prepare data for spaCy pipe
    data_tuples = list(zip(df["example"].tolist(), df["word"].tolist()))

    print(f"3. Processing {len(data_tuples)} examples with spaCy...")

    word_pos_counts = defaultdict(Counter)

    doc_stream = nlp.pipe(
        data_tuples, as_tuples=True, batch_size=BATCH_SIZE, n_process=7
    )
    for doc, target_word in tqdm(doc_stream, total=len(data_tuples)):
        target_lower = target_word.lower()
        target_doc = nlp.make_doc(target_word)
        target_tokens = [t.text.lower() for t in target_doc]
        len_target = len(target_tokens)

        if len_target == 0:
            continue

        found_pos = None

        # Scan the document for the sequence of tokens matching the target
        for i in range(len(doc) - len_target + 1):
            match = True
            for j in range(len_target):
                if doc[i + j].text.lower() != target_tokens[j]:
                    match = False
                    break

            if match:
                span = doc[i : i + len_target]
                # For MWEs (Multi-Word Expressions), the POS is defined by the root.
                # e.g., "spill the tea" -> root is "spill" (VERB)
                # e.g., "no cap" -> root is "cap" (NOUN) (depending on parse)
                found_pos = span.root.pos_
                break

        if found_pos:
            word_pos_counts[target_lower][found_pos] += 1

    print("4. Aggregating and saving...")

    # Structure for SlangLibrary: {"NOUN": ["word1", "word2"], "VERB": ...}
    final_vocab = defaultdict(list)

    for word, counts in word_pos_counts.items():
        # Get the most common POS tag for this word
        # (e.g. "cap" might be used as NOUN 50 times and VERB 20 times)
        most_common_pos, count = counts.most_common(1)[0]

        # Quality control: Ignore words that spacy thinks are just punctuation or symbols
        if most_common_pos in ["PUNCT", "SYM", "X", "SPACE"]:
            continue

        final_vocab[most_common_pos].append(word)

    # Save to JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump(final_vocab, f, indent=2)

    print(
        f"Done! Saved {sum(len(v) for v in final_vocab.values())} words to {OUTPUT_JSON}"
    )


if __name__ == "__main__":
    process_urban_dict()
