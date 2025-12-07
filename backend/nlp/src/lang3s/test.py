from typing import List

import markdown
from bs4 import BeautifulSoup
from jsonlines import jsonlines

from lang3s.app import Application
from lang3s.db import TextDatabase
from lang3s.models.topic_model import Lang3sTopicModel
from lang3s.pipeline.runner import pipeline
from lang3s_job_service import File


class Test(Application):

    def run(self):
        text_db = TextDatabase()
        topic_model = Lang3sTopicModel()
        for topic in topic_model.topics:
            print(topic.name)

        # row = session.query(Documents).filter(Documents.id == doc_id).one_or_none()
        return
        files: List[File] = []
        with jsonlines.open(
            "/Users/ik/Library/Mobile Documents/com~apple~CloudDocs/project_reddit/reddit_distortions_20251104_1319.jsonl") as reader:
            for doc in reader:
                try:
                    html_text = markdown.markdown(doc["excerpt"])
                    soup = BeautifulSoup(html_text, "html.parser")
                    content = soup.get_text()
                    files.append(File(content=content))
                except:
                    files.append(File(content=doc["excerpt"]))
                if len(files) > 2:
                    break

        docs = pipeline(files)
        with jsonlines.open("distortions_20251104_1319.jsonl", "w") as writer:
            for doc in docs:
                for sentence in doc.text.sentences:
                    for annotation in sentence.interleave("phrase_chunk"):
                        if annotation.type == "phrase_chunk":
                            print(f"[{annotation.text}|{annotation.value}]", end=" ")
                        else:
                            print(annotation.text, end=" ")
                    print("\n")
                    if sentence["distortion"] is not None:
                        writer.write({"label": sentence["distortion"],
                                      "text": sentence.text})


if __name__ == "__main__":
    Test.from_cli().run_with_plugins()
