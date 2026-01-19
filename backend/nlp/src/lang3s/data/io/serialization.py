from typing import Iterable

import jsonlines

from lang3s.shared_types import Document


def serialize(docs: Iterable[Document], file: str):
  with jsonlines.open(file, mode="w") as writer:
    for doc in docs:
      writer.write(doc.to_json())


def deserialize(file: str) -> Iterable[Document]:
  with jsonlines.open(file) as reader:
    for obj in reader:
      yield Document.from_json(obj)
