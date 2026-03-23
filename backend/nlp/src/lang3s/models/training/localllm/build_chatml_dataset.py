from jsonlines import jsonlines


def load_claim_dataset() -> list[list[dict[str, str]]]:
    data: list[list[dict[str, str]]] = []
    try:
        with jsonlines.open(
            "/Users/ik/prj/data/claim_extraction_final.jsonl"
        ) as reader:
            for obj in reader:
                prompt = f"Extract claim from: {obj['input']['before_text'].strip()} {obj['input']['target_text'].strip()}"
                target = f"{obj['claim']}"
                data.append(
                    [
                        {
                            "role": "system",
                            "content": "You are a precise information extraction engine and an expert at extracting factual claims from text.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                        {
                            "role": "assistant",
                            "content": target,
                        },
                    ]
                )
    except FileNotFoundError:
        print("Warning: claim_extraction.jsonl not found.")
        return []

    return data


def main():
    dataset = load_claim_dataset()

    with jsonlines.open(
        "/Users/ik/prj/data/claim_extraction_chatml.jsonl", "w"
    ) as writer:
        for obj in dataset:
            writer.write(obj)


if __name__ == "__main__":
    main()
