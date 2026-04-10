import argparse
import json
import math
import os
import random
import textwrap
from typing import Any

from datasets import load_dataset
from jsonlines import jsonlines
from tqdm import tqdm

random.seed(42)


def mix_datasets_with_temperature(
    datasets: dict[str, list[dict]],
    temperature: float = 2.0,
    target_total_samples: int = 200000,
) -> list[dict]:
    """
    Applies temperature scaling to balance disparate datasets.
    """
    # 1. Calculate original sizes and raw probabilities
    sizes = {name: len(data) for name, data in datasets.items() if len(data) > 0}
    total_original = sum(sizes.values())

    # 2. Apply temperature scaling T
    scaled_probs = {}
    for name, size in sizes.items():
        p_i = size / total_original
        scaled_probs[name] = math.pow(p_i, 1 / temperature)

    # 3. Normalize to get new sampling ratios
    norm_factor = sum(scaled_probs.values())
    sampling_ratios = {name: p / norm_factor for name, p in scaled_probs.items()}

    # 4. Sample the data
    mixed_dataset = []
    print(f"\n--- Temperature Scaling (T={temperature}) ---")

    for name, data in datasets.items():
        if len(data) == 0:
            continue

        # Determine how many samples this dataset gets in the final mix
        num_samples = int(sampling_ratios[name] * target_total_samples)

        # If we need more than we have, sample WITH replacement (oversampling)
        if num_samples > len(data):
            sampled = random.choices(data, k=num_samples)
        # If we need fewer than we have, sample WITHOUT replacement (downsampling)
        else:
            sampled = random.sample(data, k=num_samples)

        mixed_dataset.extend(sampled)

        print(
            f"{name:.<30} Raw: {len(data):<8} -> Scaled: {num_samples:<8} ({sampling_ratios[name]:.1%})"
        )

    random.random.shuffle(mixed_dataset)
    return mixed_dataset


def get_args():
    parser = argparse.ArgumentParser(description="Build dataset for multitask T5")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    return parser.parse_args()


def safe_load_dataset(name: str, config_name: str | None = None, split: str = "test"):
    try:
        return load_dataset(name, config_name, split=split)
    except Exception as e:
        print(f"Warning: Could not load {name} data. {e}")
        return []


def load_claim_dataset() -> list[dict[str, str]]:
    data: list[dict[str, str]] = []
    try:
        with jsonlines.open(
            "/Users/ik/prj/data/claim_extraction_final.jsonl"
        ) as reader:
            for obj in reader:
                # prompt = f"""Extract ZERO or ONE claim from the target sentence with the SOURCE of the claim.\nA CLAIM must be a statement of fact or a specific assertion about the world. It must not describe the act of speaking or comparing (e.g., avoid "X compared Y to Z" or "X said Y is like Z").\nDo not use meta-verbs like 'compared,' 'said,' or 'claimed' within the CLAIM text itself.\nThe SOURCE should be an ENTITY, AUTHOR, or UNKNOWN. DO NOT assign pronouns to the source.\nSENTENCE: {obj["input"]["target_text"]}"""
                # prompt = f"Extract claim from: {obj['input']['before_text'].strip()} {obj['input']['target_text'].strip()}"
                prompt = f"Extract claim from: {obj['input']['before_text'].strip()} {obj['input']['target_text'].strip()}"
                target = f"{obj['claim']}"
                data.append(
                    {
                        "prompt": prompt,
                        "target": target,
                    }
                )
    except FileNotFoundError:
        print("Warning: claim_extraction.jsonl not found.")
        return []

    return data


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

    random.shuffle(data)
    split_idx = math.floor(len(data) * 0.9)
    if test:
        print(f"Added {len(data) - split_idx} samples from claim dataset.")
        return data[split_idx:]
    else:
        print(f"Added {split_idx} samples from claim dataset.")
        return data[:split_idx]


def load_rte_dataset(
    test: bool, max_examples: int | None = None
) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    split = "test" if test else "train+validation"
    dataset = safe_load_dataset("SetFit/mnli", split=split)
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

    split = (
        "test_r1+test_r2+test_r3"
        if test
        else "train_r1+train_r2+train_r3+dev_r1+dev_r2+dev_r3"
    )
    label_map = {0: "entailment", 1: "neutral", 2: "contradiction"}
    dataset = safe_load_dataset("facebook/anli", split=split)
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

    random.shuffle(raw_records)

    if max_examples:
        return raw_records[:max_examples]
    return raw_records


def load_sentiment_dataset(
    test: bool, max_examples: int | None = None
) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []

    label_map = {0: "negative", 1: "neutral", 2: "positive"}
    split = "test" if test else "train+validation"
    dataset = safe_load_dataset("cardiffnlp/tweet_eval", "sentiment", split=split)
    for row in tqdm(dataset, desc="Loading cardiffnlp/tweet_eval"):
        raw_records.append(
            {
                "prompt": f"SENTIMENT: {row['text']}",
                "target": label_map[row["label"]],
            }
        )
    print(f"Added {len(raw_records)} samples from tweeteval_sentiment.")

    split = "test" if test else "train"
    dataset = safe_load_dataset("mteb/tweet_sentiment_extraction", split=split)
    for row in tqdm(dataset, desc="Loading mteb/tweet_sentiment_extraction"):
        raw_records.append(
            {
                "prompt": f"SENTIMENT: {row['text']}",
                "target": row["label_text"].lower(),
            }
        )
    print(f"Added {len(raw_records)} samples from mteb/tweet_sentiment_extraction.")

    split = "test" if test else "train"
    dataset = safe_load_dataset("FinanceMTEB/financial_phrasebank", split=split)
    for row in tqdm(dataset, desc="Loading FinanceMTEB/financial_phrasebank"):
        raw_records.append(
            {
                "prompt": f"SENTIMENT: {row['text']}",
                "target": row["label_text"].lower(),
            }
        )
    print(f"Added {len(raw_records)} samples from FinanceMTEB/financial_phrasebank.")

    random.shuffle(raw_records)
    if max_examples:
        return raw_records[:max_examples]
    return raw_records


def load_super_glue_wic_dataset(test: bool) -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []
    split = "test" if test else "train+validation"
    dataset = safe_load_dataset("aps/super_glue", "wic", split=split)
    label_map = {0: "False", 1: "True"}
    for row in tqdm(dataset, desc="Loading aps/super_glue (wic)"):
        raw_records.append(
            {
                "prompt": f"WIC: WORD: {row['word']} SENTENCE1: {row['sentence1']} SENTENCE2: {row['sentence2']}",
                "target": label_map[row["label"]],
            }
        )
    print(f"Added {len(raw_records)} samples from aps/super_glue.")
    return raw_records


def load_cognitive_dataset() -> list[dict[str, str]]:
    raw_records: list[dict[str, str]] = []

    dataset = safe_load_dataset("Koalacrown/cognitive-actions-7k", split="train+test")
    for row in tqdm(dataset, desc="Loading Koalacrown/cognitive-actions-7k"):
        raw_records.append(
            {
                "prompt": f"Determine the best COGNITIVE ACTION for the given sentence: {row['text']}",
                "target": row["primary_cognitive_action"],
            }
        )
    print(f"Added {len(raw_records)} samples from Koalacrown/cognitive-actions-7k.")

    dataset = safe_load_dataset(
        "halilbabacan/combined_synthetic_cognitive_distortions", split="train"
    )
    for row in tqdm(
        dataset,
        desc="Loading halilbabacan/combined_synthetic_cognitive_distortions",
    ):
        raw_records.append(
            {
                "prompt": f"Determine IF and WHAT COGNITIVE DISTORTION is evident in the given sentence: {row['text']}",
                "target": row["label"],
            },
        )
    print(
        f"Added {len(raw_records)} samples from halilbabacan/combined_synthetic_cognitive_distortions."
    )

    return raw_records


def format_qwen(entry):
    prompt = entry["prompt"]
    response = entry["target"]

    print(prompt)

    full_text = f"<|im_start|>system\nYou are a precise information extraction engine.<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n{response}<|im_end|>"
    return {"text": full_text}


def save_jsonl(filename, dataset):
    with open(filename, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")


def main(args):
    combined_dataset: list[dict[str, Any]] = []

    # dataset_dict = {
    #     "claim": load_claim_dataset(test=args.test),
    #     "concept_labeling": load_keyword_labeling_dataset(test=args.test),
    #     "rte": load_rte_dataset(test=args.test),
    #     "sentiment": load_sentiment_dataset(test=args.test),
    #     "super_glue": load_super_glue_wic_dataset(test=args.test),
    #     "cognitive": load_cognitive_dataset(test=args.test),
    # }
    # combined_dataset = mix_datasets_with_temperature(
    #     dataset_dict, temperature=3.0, target_total_samples=250_000
    # )

    # Claim Detection

    combined_dataset += load_claim_dataset()
    # combined_dataset += load_cognitive_dataset()

    random.shuffle(combined_dataset)
    split_idx = int(len(combined_dataset) * 0.9)
    train_data = [format_qwen(d) for d in combined_dataset[:split_idx]]
    valid_data = [format_qwen(d) for d in combined_dataset[split_idx:]]

    data_path = "/Users/ik/prj/data/qwen_mlx/"
    os.makedirs(data_path, exist_ok=True)

    save_jsonl(os.path.join(data_path, "train.jsonl"), train_data)
    save_jsonl(os.path.join(data_path, "valid.jsonl"), valid_data)


if __name__ == "__main__":
    args = get_args()
    main(args)
