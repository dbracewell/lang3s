import os

import shortuuid
from lang3s_job_service import File

from lang3s.shared_types import Metadata


def get_or_create_doc_id(file: File):
    """
    Gets the document id from the file object or generates a new one.
    """
    return file.docId or shortuuid.uuid()


def build_base_metadata(file: File, doc_id: str):
    """
    Builds base metadata for a document from the given file.
    """
    metadata = {
        Metadata.MIME_TYPE.value: file.mime_type,
    }
    if file.path is not None:
        metadata["path"] = file.path

    metadata.update(file.metadata)

    title = file.metadata.pop("title", None)
    if title is None:
        title = os.path.basename(file.path) if file.path is not None else doc_id

    return metadata, title
