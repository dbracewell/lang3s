from typing import Iterable

import msgpack

from lang3s.data.schemas import Document


def serialize(docs: Iterable[Document], file: str):
    with open(file, "wb") as writer:
        for doc in docs:
            msgpack.pack(doc.model_dump(), writer, use_bin_type=True)


def deserialize(file: str) -> Iterable[Document]:
    with open(file, "rb") as reader:
        unpacker = msgpack.Unpacker(reader, raw=False, use_list=False)
        for obj in unpacker:
            yield Document.model_validate(obj)
