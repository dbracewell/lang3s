import csv
from typing import List

from lang3s_job_service import File, JobService

from lang3s.core.doc_builder import create_document
from lang3s.pipeline.process import nlp

if __name__ == "__main__":
    docs = create_document(
        File(
            path="",
            content="John Doe met Mary Smith in Baltimore, MD last year. The United States of America is a country in North America.",
            mime_type="text/plain",
        ),
    )
    nlp([docs])
    for s in docs.text.sentences:
        for a in s.interleave("entity"):
            print(a.text)

    exit()

    job_service = JobService(
        api_key="lang3skUMvPskpvXQvKVIbsbrQEJFTGvNLjkjGpfIOZmpsMeKVfjWUobFwwmCCUcFeOzxX",
        api_host="http://localhost:3001",
    )
    files: List[File] = []
    reader = csv.DictReader(
        open("/Users/ik/Downloads/archive/data.csv"), dialect="excel"
    )
    try:
        for row in reader:
            if row["full_content"].strip() == "":
                continue
            file = File(
                path=row["url"],
                content=row["full_content"],
                mime_type="text/plain",
                metadata={
                    "title": row["title"],
                    "source": row["source_name"],
                    "author": row["author"],
                    "published_date": row["published_at"],
                },
            )
            files.append(file)
            if len(files) >= 10:
                break
    except Exception:
        pass
    job_service.annotate_documents(files=files, metadata={"tasks": []})
