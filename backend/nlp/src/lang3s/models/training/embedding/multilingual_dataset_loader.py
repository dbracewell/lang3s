import random
import unicodedata
from typing import Any, Iterator, List, Optional

from datasets import (
    load_dataset
)
from pydantic import BaseModel

# Languages in XNLI (no Japanese)
XNLI_LANGS = ["ar", "bg", "de", "el", "en", "es", "fr",
              "hi", "ru", "sw", "th", "tr", "ur", "vi", "zh"]


# -------------------------------------------------------------
# BASIC TEXT CLEANER
# -------------------------------------------------------------
def clean_text(t: str):
    if not isinstance(t, str):
        return None
    t = t.strip()
    if len(t) == 0:
        return None
    # Normalize unicode (NFKC = best for multilingual)
    t = unicodedata.normalize("NFKC", t)
    return t


def iter_ag_news_text(max_samples: Optional[int] = None, seed: int = 42) -> Iterator[str]:
    try:
        ds = load_dataset("ag_news", split="train")
    except Exception as e:
        print("[WARN] Could not load ag_news:", e)
        return iter([])
    indices = list(range(len(ds)))
    random.Random(seed).shuffle(indices)
    count = 0
    for idx in indices:
        t = clean_text(ds[idx]["text"])
        if not t:
            continue
        yield t
        count += 1
        if max_samples is not None and count >= max_samples:
            break


def iter_sst2_text(max_samples: Optional[int] = None, seed: int = 43) -> Iterator[str]:
    try:
        ds = load_dataset("sst2", split="train")
    except Exception as e:
        print("[WARN] Could not load sst2:", e)
        return iter([])
    indices = list(range(len(ds)))
    random.Random(seed).shuffle(indices)
    count = 0
    for idx in indices:
        t = clean_text(ds[idx]["sentence"])
        if not t:
            continue
        yield t
        count += 1
        if max_samples is not None and count >= max_samples:
            break


def _extract_from_lang_dict(d: Any, preferred_langs: List[str]) -> Optional[str]:
    if isinstance(d, str):
        return clean_text(d)
    if isinstance(d, dict):
        for lang in preferred_langs:
            if lang in d:
                t = clean_text(d[lang])
                if t:
                    return t
        # fallback: any valid string except metadata keys
        for k, v in d.items():
            if k in ("language", "translation"):
                continue
            t = clean_text(v)
            if t:
                return t
    return None


def iter_xnli_text(
    max_samples: Optional[int] = None,
    seed: int = 44,
    preferred_langs: Optional[List[str]] = None,
) -> Iterator[str]:
    if preferred_langs is None:
        preferred_langs = XNLI_LANGS
    try:
        ds = load_dataset("xnli", "all_languages", split="train")
    except Exception as e:
        print("[WARN] Could not load xnli:", e)
        return iter([])
    indices = list(range(len(ds)))
    random.Random(seed).shuffle(indices)
    count = 0
    for idx in indices:
        ex = ds[idx]
        t1 = _extract_from_lang_dict(ex["premise"], preferred_langs)
        t2 = _extract_from_lang_dict(ex["hypothesis"], preferred_langs)
        t = t1 or t2
        if not t:
            continue
        yield t
        count += 1
        if max_samples is not None and count >= max_samples:
            break


def iter_wiki40b_ja(max_samples: Optional[int] = None, seed: int = 43) -> Iterator[str]:
    try:
        ds = load_dataset("google/wiki40b",
                          "ja",
                          split="train")
    except Exception as e:
        print("[WARN] Could not load google/wiki40b:", e)
        return iter([])
    indices = list(range(len(ds)))
    random.Random(seed).shuffle(indices)
    count = 0
    for idx in indices:
        t = clean_text(ds[idx]["text"])
        if not t:
            continue
        yield t
        count += 1
        if max_samples is not None and count >= max_samples:
            break


def iter_livedoor_ja(max_samples: Optional[int] = None, seed: int = 43) -> Iterator[str]:
    try:
        ds = load_dataset("geniacllm/livedoor_news_corpus", split="train")
    except Exception as e:
        print("[WARN] Could not load livedoor:", e)
        return iter([])
    indices = list(range(len(ds)))
    random.Random(seed).shuffle(indices)
    count = 0
    for idx in indices:
        t = clean_text(ds[idx]["text"])
        if not t:
            continue
        yield t
        count += 1
        if max_samples is not None and count >= max_samples:
            break


def iter_tanaka_ja(max_samples: Optional[int] = None, seed: int = 43) -> Iterator[str]:
    try:
        ds = load_dataset("hpprc/tanaka-corpus", split="train")
    except Exception as e:
        print("[WARN] Could not load Tanaka:", e)
        return iter([])
    indices = list(range(len(ds)))
    random.Random(seed).shuffle(indices)
    count = 0
    for idx in indices:
        t = clean_text(ds[idx]["ja"])
        if not t:
            continue
        yield t
        count += 1
        if max_samples is not None and count >= max_samples:
            break


class DataConfig(BaseModel):
    max_total_samples: int = 1_000_000
    shard_size: int = 50_000

    # language mixture ratios
    p_en: float = 0.6
    p_ja: float = 0.4

    # per-source limits (for safety)
    max_en_ag: Optional[int] = 200_000
    max_en_sst2: Optional[int] = 100_000
    max_en_xnli: Optional[int] = 300_000


def multilingual_text_stream(cfg: DataConfig) -> Iterator[str]:
    """
    Yield a mixed stream of English + Japanese texts until cfg.max_total_samples
    is reached. Sources:
      - AG News
      - SST2
      - XNLI (EN preferred)
      - Japanese text files
    """

    # Build source iterators
    en_sources: List[Iterator[str]] = [
        iter_ag_news_text(cfg.max_en_ag, seed=cfg.max_total_samples + 1),
        iter_sst2_text(cfg.max_en_sst2, seed=cfg.max_total_samples + 2),
        iter_xnli_text(cfg.max_en_xnli, seed=cfg.max_total_samples + 3, preferred_langs=["en"]),
    ]
    # Filter out exhausted/empty ones
    en_sources = [s for s in en_sources if s is not None]

    ja_sources: List[Iterator[str]] = [
        iter_tanaka_ja(),
        iter_livedoor_ja(),
        iter_wiki40b_ja(),
    ]

    total_emitted = 0
    active_en = en_sources[:]
    active_ja = ja_sources[:]

    while total_emitted < cfg.max_total_samples and (active_en or active_ja):
        # Decide language
        r = random.random()
        use_en = (r < cfg.p_en and active_en) or not active_ja

        source_list = active_en if use_en else active_ja
        if not source_list:
            source_list = active_en or active_ja

        # pick a random source among the active ones
        i = random.randrange(len(source_list))
        src = source_list[i]

        try:
            t = next(src)
        except StopIteration:
            # remove this source
            del source_list[i]
            continue

        if not t:
            continue

        yield t
        total_emitted += 1

# # -------------------------------------------------------------
# # Extract single-language string from XNLI dict
# # (which contains all languages)
# # -------------------------------------------------------------
# def extract_xnli_text(text_dict, preferred_langs=["en"]):
#     if not isinstance(text_dict, dict):
#         return None
#
#     # Try preferred languages first
#     for lang in preferred_langs:
#         if lang in text_dict and isinstance(text_dict[lang], str):
#             t = clean_text(text_dict[lang])
#             if t:
#                 return t
#
#     # Fallback: try any valid language
#     for lang, value in text_dict.items():
#         if lang in ["language", "translation"]:
#             continue
#         if isinstance(value, str):
#             t = clean_text(value)
#             if t:
#                 return t
#
#     return None
#
#
# # -------------------------------------------------------------
# # Load XNLI (15 languages)
# # -------------------------------------------------------------
# def load_xnli(preferred_langs=["en"], max_samples=200_000):
#     print("Loading XNLI...")
#     ds = load_dataset("xnli", "all_languages", split="train")
#
#     def convert(ex):
#         t1 = extract_xnli_text(ex["premise"], preferred_langs)
#         t2 = extract_xnli_text(ex["hypothesis"], preferred_langs)
#         t = t1 if t1 else t2
#         return {"text": t}
#
#     ds = ds.map(convert, remove_columns=ds.column_names)
#     ds = ds.filter(lambda ex: isinstance(ex["text"], str))
#
#     if max_samples < len(ds):
#         ds = ds.shuffle(seed=42).select(range(max_samples))
#
#     return ds
#
#
# # -------------------------------------------------------------
# # Load English corpora for balance
# # -------------------------------------------------------------
# def load_english_corpora(max_samples=100_000):
#     print("Loading English corpora (AG News + SST2)...")
#
#     ag = load_dataset("ag_news", split="train")
#     sst = load_dataset("sst2", split="train")
#
#     # Normalize all to single column "text"
#     ag = ag.map(lambda ex: {"text": clean_text(ex["text"])},
#                 remove_columns=ag.column_names)
#     sst = sst.map(lambda ex: {"text": clean_text(ex["sentence"])},
#                   remove_columns=sst.column_names)
#
#     ag = ag.filter(lambda ex: isinstance(ex["text"], str))
#     sst = sst.filter(lambda ex: isinstance(ex["text"], str))
#
#     combined = concatenate_datasets([ag, sst]).shuffle(seed=42)
#
#     if max_samples < len(combined):
#         combined = combined.select(range(max_samples))
#
#     return combined
#
#
# def load_japanese_corpora(max_samples=300_000):
#     wiki40b: Dataset = load_dataset("google/wiki40b",
#                                     "ja",
#                                     split="train")
#     wiki40b = wiki40b.map(lambda ex: {"text": clean_text(ex["text"])},
#                           remove_columns=wiki40b.column_names)
#     wiki40b = wiki40b.filter(lambda ex: isinstance(ex["text"], str))
#
#     livedoor: Dataset = load_dataset("geniacllm/livedoor_news_corpus", split="train")
#     livedoor = livedoor.map(lambda ex: {"text": clean_text(ex["text"])},
#                             remove_columns=livedoor.column_names)
#     livedoor = livedoor.filter(lambda ex: isinstance(ex["text"], str))
#
#     tanaka: Dataset = load_dataset("hpprc/tanaka-corpus", split="train")
#     tanaka = tanaka.map(lambda ex: {"text": clean_text(ex["ja"])},
#                         remove_columns=tanaka.column_names)
#     tanaka = tanaka.filter(lambda ex: isinstance(ex["text"], str))
#
#     ds = concatenate_datasets([wiki40b, livedoor, tanaka]).shuffle(seed=42)
#     if max_samples < len(ds):
#         ds = ds.select(range(max_samples))
#
#     return ds
#
#
# # -------------------------------------------------------------
# # Combine ALL corpora
# # Balances EN, JA, and other multilingual
# # -------------------------------------------------------------
# def load_multilingual_mix_dataset(
#     size_en=150_000,
#     size_ja=300_000,
#     size_xnli=200_000,
#     seed=42
# ):
#     print("Loading multilingual + Japanese mixed dataset...")
#
#     ds_ja = load_japanese_corpora(size_ja)
#     ds_en = load_english_corpora(max_samples=size_en)
#     ds_xnli = load_xnli(
#         preferred_langs=["en"],  # Match English teacher space
#         max_samples=size_xnli
#     )
#
#     # Combine English + Japanese + XNLI multilingual
#     combined = concatenate_datasets([ds_en, ds_ja, ds_xnli])
#
#     # Shuffle & dedup
#     combined = combined.shuffle(seed=seed)
#     combined = combined.unique("text")
#
#     print("Final combined dataset size:", len(combined))
#     print("Sample:", combined[0])
#
#     return combined
