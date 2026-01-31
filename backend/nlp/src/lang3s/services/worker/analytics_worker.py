import asyncio
import json
import os
import tempfile
import traceback

from lang3s.data.db import analytics
from lang3s.data.db.filestore import FILE_STORE
from lang3s.nlp.shared_types import Metadata
from lang3s.services.client.redis_client import DUCKDB_QUEUE_NAME, redis_batch_generator


def analytics_worker(shared_state):
    db = analytics.get_db()
    try:
        while not getattr(shared_state, "should_exit", False):
            for batch in redis_batch_generator(DUCKDB_QUEUE_NAME, 200, batch_timeout=5):
                if batch:
                    if (
                        len(batch) == 1
                        and isinstance(batch[0], dict)
                        and batch[0].get("status", "") == "completed"
                    ):
                        db.execute(
                            "PRAGMA create_fts_index('text_annotations', 'id', 'text', overwrite=1);"
                        )
                        db.build_annotation_stats()
                        db.commit()
                        continue

                    print(f"WRITING {len(batch)} documents to duckdb")
                    try:
                        temp_file = None
                        with tempfile.NamedTemporaryFile(
                            mode="w+t", delete=False, suffix=".json"
                        ) as f:
                            annotations = []
                            for doc_id in batch:
                                doc = FILE_STORE.read_document(doc_id)
                                for annotation in doc.text.all_annotations:
                                    if annotation.type == "token":
                                        continue

                                    text = annotation.get(
                                        Metadata.COREF_TEXT.value, annotation.text
                                    )
                                    annotations.append(
                                        {
                                            "id": annotation.id,
                                            "text": text.upper(),
                                            "surface": text,
                                            "type": annotation.type,
                                            "mapping": f"{annotation.type}:{annotation.value}",
                                            "value": annotation.value,
                                            "sentence_aid": annotation.sentence.id,
                                            "document_id": annotation.doc_id,
                                            "embedding": annotation.embedding.tolist(),
                                            "metadata": annotation.metadata,
                                        }
                                    )
                            json.dump(annotations, f)
                            del annotations
                            f.close()
                            temp_file = f.name
                        db.execute(
                            f"INSERT OR IGNORE INTO text_annotations SELECT * FROM read_json_auto('{temp_file}');"
                        )
                        os.remove(temp_file)
                        db.commit()
                    except Exception as e:
                        print(e)
                        traceback.print_exc()
    except asyncio.CancelledError:
        print("👷 Worker: Cancelled during shutdown")
    except Exception as e:
        print(e)
        traceback.print_exc()
