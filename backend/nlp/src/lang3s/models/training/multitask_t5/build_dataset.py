import argparse
import math
import pickle
import textwrap
from random import seed, shuffle
from typing import Any

from datasets import load_dataset
from jsonlines import jsonlines
from tqdm import tqdm
from transformers import AutoTokenizer, PreTrainedTokenizer

from lang3s.models.text_generator import DEFAULT_MODEL

seed(42)


def get_args():
    parser = argparse.ArgumentParser(description="Build dataset for multitask T5")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    return parser.parse_args()


def load_claim_dataset(test: bool) -> list[dict[str, str]]:
    data: list[dict[str, str]] = []
    try:
        with jsonlines.open(
            "/Users/ik/prj/data/claim_extraction_adjudicated.jsonl"
        ) as reader:
            for obj in reader:
                prompt = textwrap.dedent(f"""CLAIM_EXTRACTION:
                                             BEFORE: {obj["input"]["before_text"]}
                                             TARGET: {obj["input"]["target_text"]}
                                             AFTER: {obj["input"]["after_text"]}""")
                target = f"CLAIM:{obj['claim']}\tLABEL:{obj['label']}\tSOURCE:{obj['source']}"
                data.append(
                    {
                        "prompt": prompt,
                        "target": target,
                    }
                )
    except FileNotFoundError:
        print("Warning: claim_extraction.jsonl not found.")
        return []

    shuffle(data)
    split_idx = math.floor(len(data) * 0.9)
    if test:
        print(f"Added {len(data) - split_idx} samples from claim dataset.")
        return data[split_idx:]
    else:
        print(f"Added {split_idx} samples from claim dataset.")
        return data[:split_idx]


def load_keyword_labeling_dataset(test: bool) -> list[dict[str, str]]:
    data: list[dict[str, str]] = []
    try:
        with jsonlines.open("/Users/ik/prj/data/keyword_category_data.jsonl") as reader:
            for example in reader:
                category = example["category"]
                keywords = example["keywords"]
                topN = list(keywords.items())
                topN = sorted(topN, key=lambda x: x[1], reverse=True)
                topN = [x[0] for x in topN[:25]]
                training_example = {
                    "prompt": f"CONCEPT_LABEL: {', '.join(topN)}",
                    "target": category,
                }
                data.append(training_example)
    except FileNotFoundError:
        print("Warning: keyword_category_data.jsonl not found.")
        return []

    shuffle(data)
    split_idx = math.floor(len(data) * 0.9)
    if test:
        print(f"Added {len(data) - split_idx} samples from claim dataset.")
        return data[split_idx:]
    else:
        print(f"Added {split_idx} samples from claim dataset.")
        return data[:split_idx]


def load_mnli_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        split = "test" if test else "train+validation"
        dataset = load_dataset("SetFit/mnli", split=split)
        for row in tqdm(dataset, desc="Loading SetFit/mnli"):
            raw_records.append(
                {
                    "prompt": textwrap.dedent(f"""RTE:
                                                  TEXT1: {row["text1"]}
                                                  TEXT2: {row["text2"]}"""),
                    "target": row["label_text"].lower(),
                }
            )
        print(f"Added {len(raw_records)} samples from SetFit/mnli.")
    except Exception as e:
        print(f"Warning: Could not load SetFit/mnli data. {e}")
    return raw_records


def load_anli_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        split = (
            "test_r1+test_r2+test_r3"
            if test
            else "train_r1+train_r2+train_r3+dev_r1+dev_r2+dev_r3"
        )
        label_map = {0: "entailment", 1: "neutral", 2: "contradiction"}
        dataset = load_dataset("facebook/anli", split=split)
        for row in tqdm(dataset, desc="Loading facebook/anli"):
            raw_records.append(
                {
                    "prompt": textwrap.dedent(f"""RTE:
                                                  TEXT1: {row["premise"]}
                                                  TEXT2: {row["hypothesis"]}"""),
                    "target": label_map[row["label"]],
                }
            )
        print(f"Added {len(raw_records)} samples from facebook/anli.")
    except Exception as e:
        print(f"Warning: Could not load facebook/anli data. {e}")
    return raw_records


def load_tweeteval_sentiment_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        label_map = {0: "negative", 1: "neutral", 2: "positive"}
        split = "test" if test else "train+validation"
        dataset = load_dataset("cardiffnlp/tweet_eval", "sentiment", split=split)
        for row in tqdm(dataset, desc="Loading cardiffnlp/tweet_eval"):
            raw_records.append(
                {
                    "prompt": f"SENTIMENT: {row['text']}",
                    "target": label_map[row["label"]],
                }
            )
        print(f"Added {len(raw_records)} samples from tweeteval_sentiment.")
    except Exception as e:
        print(f"Warning: Could not load tweeteval_sentiment data. {e}")
    return raw_records


def load_tweet_sentiment_extraction_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        split = "test" if test else "train"
        dataset = load_dataset("mteb/tweet_sentiment_extraction", split=split)
        for row in tqdm(dataset, desc="Loading mteb/tweet_sentiment_extraction"):
            raw_records.append(
                {
                    "prompt": f"SENTIMENT: {row['text']}",
                    "target": row["label_text"].lower(),
                }
            )
        print(f"Added {len(raw_records)} samples from mteb/tweet_sentiment_extraction.")
    except Exception as e:
        print(f"Warning: Could not load mteb/tweet_sentiment_extraction data. {e}")
    return raw_records


def load_financial_phrasebank_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        split = "test" if test else "train"
        dataset = load_dataset("FinanceMTEB/financial_phrasebank", split=split)
        for row in tqdm(dataset, desc="Loading FinanceMTEB/financial_phrasebank"):
            raw_records.append(
                {
                    "prompt": f"SENTIMENT: {row['text']}",
                    "target": row["label_text"].lower(),
                }
            )
        print(
            f"Added {len(raw_records)} samples from FinanceMTEB/financial_phrasebank."
        )
    except Exception as e:
        print(f"Warning: Could not load FinanceMTEB/financial_phrasebank data. {e}")
    return raw_records


def load_super_glue_wic_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        split = "test" if test else "train+validation"
        dataset = load_dataset("aps/super_glue", "wic", split=split)
        label_map = {0: "False", 1: "True"}
        for row in tqdm(dataset, desc="Loading aps/super_glue (wic)"):
            raw_records.append(
                {
                    "prompt": f"WIC: WORD: {row['word']} SENTENCE1: {row['sentence1']} SENTENCE2: {row['sentence2']}",
                    "target": label_map[row["label"]],
                }
            )
        print(f"Added {len(raw_records)} samples from aps/super_glue.")
    except Exception as e:
        print(f"Warning: Could not load aps/super_gluedata. {e}")
    return raw_records


def load_cognitive_actions_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        split = "test" if test else "train"
        dataset = load_dataset("Koalacrown/cognitive-actions-7k", split=split)
        for row in tqdm(dataset, desc="Loading Koalacrown/cognitive-actions-7k"):
            raw_records.append(
                {
                    "prompt": f"COGNITIVE_ACTION: {row['text']}",
                    "target": row["primary_cognitive_action"],
                }
            )
        print(f"Added {len(raw_records)} samples from Koalacrown/cognitive-actions-7k.")
    except Exception as e:
        print(f"Warning: Could not load Koalacrown/cognitive-actions-7k. {e}")
    return raw_records


def load_cognitive_distortions_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    try:
        if test:
            return []
        dataset = load_dataset(
            "halilbabacan/combined_synthetic_cognitive_distortions", split="train"
        )
        for row in tqdm(
            dataset,
            desc="Loading halilbabacan/combined_synthetic_cognitive_distortions",
        ):
            raw_records.append(
                {
                    "prompt": f"COGNITIVE_DISTORTION: {row['text']}",
                    "target": row["label"],
                }
            )
        print(
            f"Added {len(raw_records)} samples from halilbabacan/combined_synthetic_cognitive_distortions."
        )
    except Exception as e:
        print(
            f"Warning: Could not load halilbabacan/combined_synthetic_cognitive_distortions. {e}"
        )
    return raw_records


def tokenize_data(
    data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tokenizer: PreTrainedTokenizer = AutoTokenizer.from_pretrained(DEFAULT_MODEL)
    tokenized_data: list[dict[str, Any]] = []

    max_source_length = 2048
    max_target_length = 2048

    for example in tqdm(data, desc="Tokenizing data"):
        model_inputs = tokenizer(
            example["prompt"],
            max_length=max_source_length,
            truncation=True,
            padding=False,
            return_tensors=None,  # Return lists instead of tensors for the collator
        )
        labels = tokenizer(
            example["target"],
            max_length=max_target_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )
        model_inputs["labels"] = labels["input_ids"]
        tokenized_data.append(model_inputs)
    return tokenized_data


def main(args):
    combined_dataset: list[dict[str, Any]] = []

    # Claim Detection
    combined_dataset += load_claim_dataset(test=args.test)

    # Concept Labelling Dataset
    load_keyword_labeling_dataset(test=args.test)

    # Textual Entailment
    combined_dataset += load_mnli_dataset(test=args.test)
    combined_dataset += load_anli_dataset(test=args.test)

    # Sentiment
    combined_dataset += load_tweeteval_sentiment_dataset(test=args.test)
    combined_dataset += load_tweet_sentiment_extraction_dataset(test=args.test)
    combined_dataset += load_financial_phrasebank_dataset(test=args.test)

    # Word In Context
    combined_dataset += load_super_glue_wic_dataset(test=args.test)

    # Cognitive
    combined_dataset += load_cognitive_actions_dataset(test=args.test)
    combined_dataset += load_cognitive_distortions_dataset(test=args.test)

    shuffle(combined_dataset)

    payload = tokenize_data(combined_dataset)
    with open(f"/Users/ik/prj/data/t5_{'test' if args.test else 'train'}", "wb") as f:
        pickle.dump(payload, f)


if __name__ == "__main__":
    args = get_args()
    main(args)
