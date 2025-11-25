from typing import List

from jsonlines import jsonlines

from lang3s.app import Application
from lang3s.pipeline.runner import pipeline
from lang3s_job_service import File


class Test(Application):

    def run(self):
        files: List[File] = []
        with jsonlines.open(
            "/Users/ik/Library/Mobile Documents/com~apple~CloudDocs/project_reddit/reddit_distortions_20251104_1319.jsonl") as reader:
            for doc in reader:
                files.append(File(content=doc["excerpt"]))
                if len(files) > 100:
                    break

        docs = pipeline(files)
        with jsonlines.open("distortions_20251104_1319.jsonl", "w") as writer:
            for doc in docs:
                for sentence in doc.text.sentences:
                    if sentence["distortion"] is not None:
                        writer.write({"label": sentence["distortion"],
                                      "text": sentence.text})


if __name__ == "__main__":
    Test.from_cli().run_with_plugins()
