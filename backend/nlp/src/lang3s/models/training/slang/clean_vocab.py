import json

import nltk
from nltk.corpus import brown, stopwords, words

from lang3s.data.db.filestore import FILE_STORE

# Configuration
INPUT_FILE = FILE_STORE.get_file_path("slang_vocab.json")
OUTPUT_FILE = FILE_STORE.get_file_path("slang_vocab_clean.json")

# List of words that ARE standard English but we specifically want to KEEP
# because they represent common semantic shifts (Polysemous Slang).
POLYSEMOUS_KEEP_LIST = {
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
    "serve",
    "read",
    "clock",
    "gag",
    "ate",
    "mother",
    "daddy",
    "zaddy",
    "snack",
    "cake",
    "fruit",
    "camp",
}


def clean_vocab():
    print("Loading dictionaries...")
    try:
        nltk.data.find("corpora/words")
        nltk.data.find("corpora/brown")
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("words")
        nltk.download("brown")
        nltk.download("stopwords")

    # Build a robust set of "Standard English"
    # We use lower case for comparison
    standard_vocab = set(w.lower() for w in words.words())
    standard_vocab.update(w.lower() for w in brown.words() if w.isalpha())
    standard_vocab.update(stopwords.words("english"))

    # Load the dirty slang vocab
    with open(INPUT_FILE, "r") as f:
        data = json.load(f)

    cleaned_data = {}
    removed_count = 0
    kept_count = 0

    print(f"Cleaning {INPUT_FILE}...")

    for pos, word_list in data.items():
        cleaned_list = []
        for word in word_list:
            w_lower = word.lower()

            # CONDITION 1: Keep if it's on our explicit Polysemous whitelist
            if w_lower in POLYSEMOUS_KEEP_LIST:
                cleaned_list.append(word)
                kept_count += 1
                continue

            # CONDITION 2: Remove if it's a known Standard English word
            if w_lower in standard_vocab:
                # print(f"Removing standard word: {word}") # Uncomment to see what's going
                removed_count += 1
                continue

            # CONDITION 3: Remove very short words (noise/abbreviations often handled by tokenizer)
            if len(word) < 3:
                removed_count += 1
                continue

            # Keep otherwise (Likely true OOV slang like 'yeet', 'rizz')
            cleaned_list.append(word)
            kept_count += 1

        if cleaned_list:
            cleaned_data[pos] = cleaned_list

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(cleaned_data, f, indent=2)

    print("-" * 30)
    print(f"Removed {removed_count} standard/noise words.")
    print(f"Kept {kept_count} slang candidates.")
    print(f"Saved to {OUTPUT_FILE}")
    print("-" * 30)
    print("NEXT STEPS:")
    print("1. Update 'build_dataset.py' to use 'slang_vocab_clean.json'")
    print("2. Re-run 'build_dataset.py'")
    print("3. Re-run 'train_slang_detector.py'")


if __name__ == "__main__":
    clean_vocab()
