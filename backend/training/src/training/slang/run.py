import re
from collections import Counter
from typing_extras import List

import nltk
import torch
from tqdm import tqdm
from transformers import AutoModelForTokenClassification, AutoTokenizer

from lang3s.data.filestore import FILE_STORE
from lang3s.data.io.serialization import deserialize

MODEL_PATH = FILE_STORE.get_file_path("slang-detector-model/final")


class SlangPredictor:
    def __init__(self, model_path: str = "slang-detector-model/final"):
        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
        print(f"Loading model from {model_path} on {self.device}...")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForTokenClassification.from_pretrained(model_path)
            self.model.to(self.device)
            self.model.eval()
        except OSError:
            raise OSError(
                f"Could not load model from {model_path}. Ensure you have run 'train_slang_detector.py' first."
            )

        self.id2label = self.model.config.id2label

        # --- FILTERS ---

        # 1. Download Standard Dict if needed
        try:
            nltk.data.find("corpora/words")
        except LookupError:
            nltk.download("words")
        from nltk.corpus import words

        self.standard_vocab = set(w.lower() for w in words.words())

        # 2. Hard ignore list (Stopwords, Auxiliaries, Numbers)
        self.ignore_tokens = {
            "n't",
            "nt",
            "'s",
            "'d",
            "'ll",
            "'re",
            "'ve",
            "'m",
            "m",
            "s",
            "wo",
            "ca",
            "sha",
            "na",
            "gon",
            "wan",
            "do",
            "did",
            "does",
            "doing",
            "done",
            "is",
            "are",
            "was",
            "were",
            "been",
            "have",
            "has",
            "had",
            "having",
            "get",
            "got",
            "getting",
            "gotten",
            "just",
            "really",
            "very",
            "super",
            "so",
            "too",
            "literally",
            "totally",
            "actually",
            "and",
            "but",
            "or",
            "if",
            "because",
            "as",
            "than",
            "the",
            "a",
            "an",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "its",
            "our",
            "their",
            "mine",
            "yours",
            "hers",
            "ours",
            "theirs",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "these",
            "those",
            "here",
            "there",
            "where",
            "when",
            "why",
            "how",
            "all",
            "any",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "love",
            "hate",
            "good",
            "bad",
            "wrong",
            "right",  # Common sentiments
            "girl",
            "boy",
            "man",
            "woman",
            "guy",
            "guys",
            "male",
            "female",  # Common demographics
        }

        # 3. Whitelist: Words that ARE in dictionary but we want to detect anyway
        self.polysemous_whitelist = {
            "cap",
            "tea",
            "beef",
            "sick",
            "wicked",
            "ghost",
            "salty",
            "shade",
            "drip",
            "flex",
            "mid",
            "basic",
            "cracked",
            "fire",
            "lit",
            "bet",
            "slay",
            "stan",
            "ratio",
            "tool",
            "feed",
            "bot",
            "sub",
            "mod",
        }

        self.ignore_patterns = [
            re.compile(r"^\d+[fFmM]?$"),  # Age/Gender tags (23f) or numbers
            re.compile(r"^[^\w\s]+$"),  # Punctuation only
        ]

    def _should_ignore(self, token: str, is_title_case: bool) -> bool:
        token_lower = token.lower()

        # 1. Hard Ignore List
        if token_lower in self.ignore_tokens:
            return True

        # 2. Regex Patterns
        for pattern in self.ignore_patterns:
            if pattern.match(token):
                return True

        # 3. Dictionary Filter
        # If it is a standard word AND not on our specific whitelist, ignore it.
        # This kills "God", "Islam", "Church" (Standard words)
        if token_lower in self.standard_vocab:
            if token_lower not in self.polysemous_whitelist:
                return True

        # 4. Heuristic: Proper Nouns / Entities
        # If it's Title Case (e.g., "Islam", "ChatGPT") and wasn't whitelisted above, ignore.
        # Note: We trust the input casing here.
        if is_title_case:
            return True

        return False

    def predict(self, tokenized_sentences: List[List[str]]) -> List[List[str]]:
        if not tokenized_sentences:
            return []

        inputs = self.tokenizer(
            tokenized_sentences,
            is_split_into_words=True,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=128,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        predictions = torch.argmax(outputs.logits, dim=2)

        batch_results = []

        for i, sentence_preds in enumerate(predictions):
            word_ids = inputs.word_ids(batch_index=i)
            input_tokens = tokenized_sentences[i]

            # Map sub-tokens to whole words
            word_pred_map = {}
            for idx, word_idx in enumerate(word_ids):
                if word_idx is None:
                    continue
                if word_idx not in word_pred_map:
                    word_pred_map[word_idx] = []
                word_pred_map[word_idx].append(sentence_preds[idx].item())

            detected_slang = []
            current_phrase = []

            for word_idx in range(len(input_tokens)):
                token = input_tokens[word_idx]

                # Check ignores (contextual title case check)
                is_title = token[0].isupper() and word_idx > 0
                should_skip = False  # self._should_ignore(token, is_title)

                # Get prediction IDs for this word (from its sub-tokens)
                subword_preds = word_pred_map.get(word_idx, [0])  # Default O

                # Heuristic:
                # If any subtoken is B (1), treat word as Beginning.
                # If no B, but has I (2), treat as Inside.
                is_start = 1 in subword_preds
                is_inside = 2 in subword_preds and not is_start

                if should_skip:
                    # If we skip a word, it breaks any current phrase
                    if current_phrase:
                        detected_slang.append(" ".join(current_phrase))
                        current_phrase = []
                    continue

                if is_start:
                    # Found a new B-tag.
                    # 1. Close previous phrase if exists
                    if current_phrase:
                        detected_slang.append(" ".join(current_phrase))
                    # 2. Start new phrase
                    current_phrase = [token]

                elif is_inside:
                    # Found an I-tag.
                    if current_phrase:
                        current_phrase.append(token)
                    else:
                        # "Orphan" I-tag (e.g., model predicted I without B).
                        # Treat it as a start to be safe/lenient.
                        current_phrase = [token]

                else:
                    # Found O (0). Close current phrase.
                    if current_phrase:
                        detected_slang.append(" ".join(current_phrase))
                        current_phrase = []

            # End of sentence: Close any trailing phrase
            if current_phrase:
                detected_slang.append(" ".join(current_phrase))

            batch_results.append(detected_slang)

        return batch_results


if __name__ == "__main__":
    predictor = SlangPredictor(str(MODEL_PATH))
    processed = 0
    to_process = 9000

    counter = Counter()
    for doc in tqdm(deserialize("/Users/ik/prj/Lang3s/reddit.docs"), total=to_process):
        sentences = [
            [t.text for t in sentence.tokens] for sentence in doc.text.sentences
        ]
        predicted = predictor.predict(tokenized_sentences=sentences)
        for p in predicted:
            if p:
                counter[" ".join(p).lower()] += 1
        processed += 1
        if processed > to_process:
            break

    for phrase, count in counter.most_common(150):
        print(phrase, count)
