from jsonlines import jsonlines


def main():
    input_filename = "/Users/ik/prj/data/claim_extraction_final.jsonl"
    output_filename = "/Users/ik/prj/data/claim_extraction_t5.jsonl"
    with jsonlines.open(output_filename, "w") as writer:
        with jsonlines.open(input_filename) as reader:
            for example in reader:
                before_text = example["input"]["before_text"]
                target_text = example["input"]["target_text"]
                claim = example["claim"] or "NO CLAIM"
                source = example["source"] or "NO SOURCE"
                writer.write(
                    {
                        "input": f"{before_text} {target_text}",
                        "output": f"claim: {claim} source: {source}",
                    }
                )


if __name__ == "__main__":
    main()
