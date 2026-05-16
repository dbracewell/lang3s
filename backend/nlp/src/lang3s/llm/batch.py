import jsonlines

from lang3s.llm import Message


def create_batch_job_file(
    data: list[list[Message]],
    model: str,
    output_file: str,
) -> None:
    with jsonlines.open(output_file, mode="w") as writer:
        for index, messages in enumerate(data):
            job = {
                "custom_id": f"request-{index}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [m.to_dict() for m in messages],
                },
            }
            writer.write(job)
