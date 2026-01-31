from jsonlines import jsonlines
from lang3s_job_service import File

from lang3s import config
from lang3s.app import Application
from lang3s.pipeline import pipeline


class Test(Application):
    def run(self):
        print(config.EMBEDDING_MODEL)
        with jsonlines.open("/Users/ik/prj/Lang3s/news.jsonl") as reader:
            files = [File(content=doc["content"]) for doc in reader]
        docs = pipeline(files[:1])
        for doc in docs:
            for event in doc.text.events:
                print(event.trigger.sentence)
                print(event)
            for entity in doc.text.entities:
                print(entity, " => ", entity.parent)


if __name__ == "__main__":
    Test.from_cli().run()
