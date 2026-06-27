from typing import Literal

import duckdb

from lang3s.core import config
from lang3s.core.typing_extras import SingletonMeta
from lang3s.data import filestore

from .query_template import QueryTemplateEngine


class AnalyticsDB(metaclass=SingletonMeta):
    def __init__(self):
        self.queries = QueryTemplateEngine()
        first_run = not filestore.get_analytics_db_path().exists()
        self.connection = duckdb.connect(filestore.get_analytics_db_path())
        self.connection.execute(
            self.queries.render(
                "duckdb_init.sql.j2",
                DB_USER=config.DB_USER,
                DB_PASSWORD=config.DB_PASSWORD,
                DB_HOST=config.DB_HOST,
                DB_PORT=config.DB_PORT,
            )
        )
        if first_run:
            self.build_annotation_stats()

    def build_annotation_stats(self):
        self.execute(self.queries.render("annotation_stats_builder.sql.j2"))
        self.commit()

    def run_query(
        self,
        template_name: str,
        parameters: object | None = None,
        return_format: Literal["raw", "df", "records"] = "records",
        **kwargs,
    ):
        query = self.queries.render(template_name, **kwargs)
        return self.execute(query, parameters, return_format)

    def execute(
        self,
        query: str,
        parameters: object | None = None,
        return_format: Literal["raw", "df", "records"] = "raw",
    ):
        val = self.connection.execute(query, parameters)
        if return_format == "raw":
            return val
        elif return_format == "df":
            return val.df()
        else:
            return val.df().to_dict(orient="records")

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


analytics_db: AnalyticsDB = None  # type: ignore


def init_analytics_db():
    global analytics_db
    if analytics_db is None:
        analytics_db = AnalyticsDB()


def get_analytics_db():
    global analytics_db
    if analytics_db is None:
        init_analytics_db()
    return analytics_db


def shutdown_analytics_db():
    global analytics_db
    if analytics_db is not None:
        analytics_db.close()
