import sys
import time
from pathlib import Path
from typing import Literal

import requests
from jsonlines import jsonlines

from lang3s.data.parsers.text.markdown import parse_markdown


class RedditCrawler:
    def __init__(
        self,
        corpus: str | Path,
        user_agent="Mozilla/5.0 (compatible; CulturalAI_Bot/1.0; +http://example.com)",
    ):
        self.headers = {"User-Agent": user_agent}
        self.parser = parse_markdown
        self.seen_ids = set()
        self.corpus = Path(corpus)
        self.__load_existing_ids()

    def __load_existing_ids(self):
        """Pre-populates seen_ids from an existing
        dataset to prevent duplicates on restart."""
        if self.corpus.exists():
            with jsonlines.open(self.corpus) as reader:
                for doc in reader:
                    if "id" in doc:
                        self.seen_ids.add(doc["id"])

    def fetch_posts(
        self,
        subreddit: str,
        category: Literal["new", "hot", "top"] = "hot",
        limit: int = 100,
    ):
        """
        Hits the public JSON endpoint: https://www.reddit.com/r/{subreddit}/{category}.json
        """
        url = f"https://www.reddit.com/r/{subreddit}/{category}.json?limit={limit}"
        try:
            response = requests.get(url, headers=self.headers)

            # Simple rate limit handling
            if response.status_code == 429:
                print(f"  [429] Rate limited on r/{subreddit}. Waiting 5 seconds...")
                time.sleep(5)
                response = requests.get(url, headers=self.headers)

            if response.status_code != 200:
                print(
                    f"  [Error] Failed to fetch r/{subreddit}: "
                    f"Status {response.status_code}"
                )
                return []

            data = response.json()
            posts = []

            children = data.get("data", {}).get("children", [])
            for child in children:
                posts.append(child.get("data", {}))

            return posts
        except Exception as e:
            print(f"  [Exception] Error fetching r/{subreddit}: {e}")
            return []

    def crawl(
        self,
        subreddits: list[str],
        interval: int = 10,
    ):
        try:
            while True:
                new_docs = []

                for sub_name in subreddits:
                    print(f"Fetching r/{sub_name}")

                    # Fetch New, Hot, and Top to ensure we catch updates and quality
                    # We split the limit among the 3 categories
                    req_limit = 100

                    categories = ["new", "hot", "top"]

                    all_posts = []

                    for cat in categories:
                        posts = self.fetch_posts(sub_name, cat, req_limit)  # type:ignore
                        all_posts.extend(posts)
                        time.sleep(1.0)

                    for post in all_posts:
                        post_id = post.get("id")

                        # Deduplication check
                        if not post_id or post_id in self.seen_ids:
                            continue

                        selftext: str = post.get("selftext", "")

                        # Skip if mostly image/link or empty
                        if not selftext or len(selftext) < 50:
                            continue

                        clean_text = self.parser(selftext).content

                        self.seen_ids.add(post_id)
                        new_docs.append(
                            {
                                "text": clean_text,
                                "source": f"r/{sub_name}",
                                "title": post.get("title", ""),
                                "author": post.get("author", ""),
                                "id": post_id,
                                "fetched_at": time.time(),
                            }
                        )

                print(f"--- Batch Complete. Found {len(new_docs)} new documents. ---")

                if new_docs:
                    self.seen_ids.update(set([doc["id"] for doc in new_docs]))
                    with jsonlines.open(self.corpus, mode="a") as writer:
                        for doc in new_docs:
                            writer.write(doc)
                    print(
                        f"Saved updated corpus ({len(new_docs)} total docs) "
                        f"to {self.corpus}"
                    )
                else:
                    print("No new documents found this cycle.")

                print(f"Sleeping for {interval} minutes...")
                time.sleep(interval * 60)

        except KeyboardInterrupt:
            print("\n\nStopping monitor. Data is safe.")
            sys.exit(0)
