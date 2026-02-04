from typing import Iterable

import msgpack

from lang3s.nlp.shared_types import Document


def serialize(docs: Iterable[Document], file: str):
    with open(file, "wb") as writer:
        for doc in docs:
            msgpack.pack(doc.to_json(), writer, use_bin_type=True)


def deserialize(file: str) -> Iterable[Document]:
    with open(file, "rb") as reader:
        unpacker = msgpack.Unpacker(reader, raw=False, use_list=False)
        for unpacked_doc in unpacker:
            yield Document.from_json(unpacked_doc)
