from jsonlines import jsonlines

from lang3s.pipeline import pipeline
from lang3s_job_service import File
from .app import Application


class Test(Application):

    def run(self):
        # with jsonlines.open("distortion_detection.jsonl", "w") as writer:
        #     with jsonlines.open('/Users/ik/Downloads/data/thinking_traps_clean.jsonl') as reader:
        #         for doc in reader:
        #             label = "Distorted"
        #             if doc["label"] == "Not Distorted":
        #                 label = "Not Distorted"
        #             writer.write({"label": label, "text": doc["text"]})
        # exit()
        files = []
        with jsonlines.open(
            "/Users/ik/Library/Mobile Documents/com~apple~CloudDocs/project_reddit/reddit_distortions_20251104_1319.jsonl") as reader:
            for doc in reader:
                files.append(File(content=doc["excerpt"]))
        # files = [File(
        #     content="Layer 4: Tool Stack\n\nhttps://preview.redd.it/sk2u2vhoiazf1.png?width=1024&amp;format=png&amp;auto=webp&amp;s=4cdeb746afbd8b74ca90a2d11b791c0cb61ed4bb\n\nBeyond the browser setup, here's what I use:\n\n**Social Media Management**: ")]
        docs = pipeline(files[:10])

        with jsonlines.open("distortions_20251104_1319.jsonl", "w") as writer:
            for doc in docs:
                for sentence in doc.text.sentences:
                    if sentence["distortion"] is not None:
                        writer.write({"label": sentence["distortion"],
                                      "text": sentence.text})


if __name__ == "__main__":
    Test.from_cli().run_with_plugins()
