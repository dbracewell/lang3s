import csv
from typing import List

from lang3s.job_service import File, JobService

if __name__ == "__main__":
    job_service = JobService(api_key="456789")
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
            break
    except Exception:
        pass
    job_service.annotate_documents(files=files)
