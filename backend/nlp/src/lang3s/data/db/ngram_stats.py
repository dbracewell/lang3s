import pickle
import sqlite3

import numpy as np


class NGramDatabase:
    """
    A persistent, dictionary-like store for n-gram counts and embeddings.
    Uses SQLite to manage memory efficiently for massive corpora.
    """

    def __init__(self, db_path="background_corpus.db"):
        self.conn = sqlite3.connect(db_path)
        # WAL mode allows concurrent readers and faster writes
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS counts (key BLOB PRIMARY KEY, count INTEGER)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS embeddings (key BLOB PRIMARY KEY, vector BLOB)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS ngram_statistics (key INTEGER PRIMARY KEY, count INTEGER)"
        )
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def increment_total_n(self, counter_dict):
        if not counter_dict:
            return
        # Use ON CONFLICT to add to existing counts
        data = [(k, v, v) for k, v in counter_dict.items()]
        self.conn.executemany(
            """
            INSERT INTO ngram_statistics (key, count)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET count = count + ?
            """,
            data,
        )
        self.conn.commit()

    def get_count(self, key):
        k_bytes = pickle.dumps(key)
        cursor = self.conn.execute("SELECT count FROM counts WHERE key=?", (k_bytes,))
        res = cursor.fetchone()
        return res[0] if res else 0

    def batch_increment(self, counter_dict):
        """
        Updates counts in bulk. Much faster than individual updates.
        :param counter_dict: dict or Counter of {ngram_tuple: count}
        """
        if not counter_dict:
            return
        # Use ON CONFLICT to add to existing counts
        data = [(pickle.dumps(k), v, v) for k, v in counter_dict.items()]
        self.conn.executemany(
            """
                              INSERT INTO counts (key, count) VALUES (?, ?)
                              ON CONFLICT(key) DO UPDATE SET count = count + ?
                              """,
            data,
        )
        self.conn.commit()

    def __getitem__(self, key):
        return self.get_count(key)

    def __contains__(self, key):
        k_bytes = pickle.dumps(key)
        cursor = self.conn.execute("SELECT 1 FROM counts WHERE key=?", (k_bytes,))
        return cursor.fetchone() is not None

    def __setitem__(self, key, value):
        # Acts as a direct set (overwrite), not increment
        k_bytes = pickle.dumps(key)
        self.conn.execute(
            "INSERT OR REPLACE INTO counts (key, count) VALUES (?, ?)", (k_bytes, value)
        )
        self.conn.commit()

    def get_total_tokens(self):
        r = self.conn.execute("SELECT * FROM ngram_statistics where key = 1").fetchone()
        return r[1] if r else 0

    def store_embedding(self, key, vector):
        k_bytes = pickle.dumps(key)
        # Ensure vector is a numpy array
        if not isinstance(vector, np.ndarray):
            vector = np.array(vector)
        v_bytes = vector.tobytes()
        self.conn.execute(
            "INSERT OR REPLACE INTO embeddings (key, vector) VALUES (?, ?)",
            (k_bytes, v_bytes),
        )
        self.conn.commit()

    def get_embedding(self, key, dtype=np.float32):
        k_bytes = pickle.dumps(key)
        cursor = self.conn.execute(
            "SELECT vector FROM embeddings WHERE key=?", (k_bytes,)
        )
        res = cursor.fetchone()
        if res:
            return np.frombuffer(res[0], dtype=dtype)
        return None
