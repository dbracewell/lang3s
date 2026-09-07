from lang3s.client.job_service import JobService
from lang3s.core.io.formats import InputFileType


def main():
    jobs = JobService(
        api_host="http://localhost:8003",
        api_key="lang3s-api-key-RTUroifaPcbmANuONcdisVOmraqrpMqSwVYhLpqBWzkxnOWHxogskKyPKyQrJdkE",
    )
    jobs.annotate(
        InputFileType.JSON_LINES.read(
            "/Users/david/prj/data/news.jsonl",
            schema_info={"text_column": "content"},
        )
    )


if __name__ == "__main__":
    main()
