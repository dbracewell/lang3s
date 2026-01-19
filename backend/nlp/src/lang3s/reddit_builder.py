import json
import os
import random
import re
import sys
import time

import markdown
import requests
from bs4 import BeautifulSoup


class MarkdownCleaner:
    @staticmethod
    def to_text(md_text):
        """
        Robustly converts Reddit Markdown to plain text.
        1. Converts Markdown -> HTML
        2. Uses BeautifulSoup to strip tags
        3. Removes artifacts like URLs and excessive whitespace
        """
        if not md_text:
            return ""

        # 1. Convert Markdown to HTML
        # extensions=['extra'] covers tables, footnotes, etc. often found on Reddit
        try:
            html = markdown.markdown(md_text, extensions=["extra"])
        except Exception:
            # Fallback for complex/broken markdown
            html = md_text

        # 2. Extract Text from HTML
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ")

        # 3. Post-cleaning
        # Remove URLs (they are style-neutral and add noise)
        text = re.sub(r"http\S+", "", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text


class RedditJSONFetcher:
    def __init__(
        self,
        user_agent="Mozilla/5.0 (compatible; CulturalAI_Bot/1.0; +http://example.com)",
    ):
        # Reddit STRICTLY requires a custom User-Agent for the JSON API
        self.headers = {"User-Agent": user_agent}
        self.cleaner = MarkdownCleaner()
        self.seen_ids = set()

    def load_existing_ids(self, corpus):
        """Pre-populates seen_ids from an existing dataset to prevent duplicates on restart."""
        count = 0
        for doc in corpus:
            if "id" in doc:
                self.seen_ids.add(doc["id"])
                count += 1
        print(f"Tracker initialized with {count} existing post IDs.")

    def fetch_posts(self, subreddit, category="hot", limit=50):
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
                    f"  [Error] Failed to fetch r/{subreddit}: Status {response.status_code}"
                )
                return []

            data = response.json()
            posts = []

            # Navigate JSON structure: data -> children -> data -> selftext
            children = data.get("data", {}).get("children", [])
            for child in children:
                posts.append(child.get("data", {}))

            return posts
        except Exception as e:
            print(f"  [Exception] Error fetching r/{subreddit}: {e}")
            return []

    def fetch_corpus(self, limit_per_sub=100):
        """
        Fetches from subreddits selected specifically for STYLE contrast.
        """
        # We target 3 distinct style clusters:
        targets = {
            "Academic/Formal": ["AskHistorians", "science", "philosophy"],
            "Narrative/Casual": ["AskReddit", "TIFU", "relationship_advice"],
            "Slang/Digital/Emoji": ["WallStreetBets", "Teenagers", "Copypasta"],
            "Over50": ["OverFifty"],
            "Over30": ["AskMenOver30", "AskWomenOver30"],
            "Over20": ["twenties", "EarlyTwenties"],
            "GenZ": ["GenZ"],
            "Millennials": ["Millennials"],
            "GenX": ["GenX"],
            "Christianity": ["Christianity"],
            "islam": ["islam"],
            "Buddhism": ["Buddhism"],
            "midwest": ["midwest"],
        }

        new_docs = []

        print(f"--- Fetching batch (Limit: ~{limit_per_sub} posts per sub) ---")

        for style, subs in targets.items():
            for sub_name in subs:
                print(f"Fetching r/{sub_name} ({style})...")

                # Fetch New, Hot, and Top to ensure we catch updates and quality
                # We split the limit among the 3 categories
                req_limit = max(10, limit_per_sub // 3)

                categories = ["new", "hot", "top"]
                all_posts = []

                for cat in categories:
                    posts = self.fetch_posts(sub_name, cat, req_limit)
                    all_posts.extend(posts)
                    # Be polite to the API between category calls
                    time.sleep(1.0)

                for post in all_posts:
                    post_id = post.get("id")

                    # Deduplication check
                    if not post_id or post_id in self.seen_ids:
                        continue

                    selftext = post.get("selftext", "")

                    # Skip if mostly image/link or empty
                    if not selftext or len(selftext) < 50:
                        continue

                    clean_text = self.cleaner.to_text(selftext)

                    self.seen_ids.add(post_id)
                    new_docs.append(
                        {
                            "text": clean_text,
                            "source": f"r/{sub_name}",
                            "expected_style": style,
                            "id": post_id,
                            "fetched_at": time.time(),
                        }
                    )

        print(f"--- Batch Complete. Found {len(new_docs)} new documents. ---")
        return new_docs


class SyntheticGenerator:
    """
    Generates mock Reddit data for testing the pipeline without internet access.
    """

    @staticmethod
    def generate_corpus(n_per_style=50):
        print(f"--- Generating Synthetic Data ({n_per_style * 3} docs) ---")
        corpus = []

        # 1. Academic Style
        academic_phrases = [
            "The empirical evidence suggests a divergence.",
            "Methodologically speaking,",
            "Furthermore, the citation provided indicates",
            "In the context of the late 19th century,",
            "One must consider the socio-economic implications.",
            "The hypothesis was rejected.",
        ]

        # 2. Narrative Style
        narrative_phrases = [
            "So I went to the store yesterday and",
            "TIFU by accidentally deleting my boss's files.",
            "My (25F) boyfriend (26M) keeps forgetting",
            "I honestly don't know what to do anymore.",
            "Edit: Thanks for the gold kind stranger!",
            "Long time lurker, first time poster.",
        ]

        # 3. Slang/Emoji Style
        slang_phrases = [
            "🚀🚀 TO THE MOON 🚀🚀",
            "LITERALLY dying rn 💀💀",
            "no cap this is fire fr",
            "bruh moment",
            "YOLO into 0DTE calls",
            "diamond hands 💎🙌",
            "based and redpilled",
            "sheeeesh",
        ]

        # Generate mixed documents
        for _ in range(n_per_style):
            # Academic
            text = " ".join(random.choices(academic_phrases, k=5))
            corpus.append(
                {
                    "text": text,
                    "source": "synthetic_academic",
                    "expected_style": "Academic",
                    "id": str(random.random()),
                }
            )

            # Narrative
            text = " ".join(random.choices(narrative_phrases, k=6))
            corpus.append(
                {
                    "text": text,
                    "source": "synthetic_narrative",
                    "expected_style": "Narrative",
                    "id": str(random.random()),
                }
            )

            # Slang
            text = " ".join(random.choices(slang_phrases, k=8))
            corpus.append(
                {
                    "text": text,
                    "source": "synthetic_slang",
                    "expected_style": "Slang",
                    "id": str(random.random()),
                }
            )

        return corpus


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build a Reddit corpus for Style Analysis"
    )
    parser.add_argument(
        "--use_synthetic", action="store_true", help="Force usage of synthetic data"
    )
    parser.add_argument(
        "--output", default="reddit_style_corpus.json", help="Output file"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Minutes between checks (0 for single run)",
    )

    args = parser.parse_args()

    corpus = []

    # 1. Load existing data (to prevent duplicates)
    if os.path.exists(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                corpus = json.load(f)
            print(f"Loaded {len(corpus)} existing documents from {args.output}")
        except json.JSONDecodeError:
            print("Output file exists but is invalid JSON. Starting fresh.")
            corpus = []

    if args.use_synthetic:
        # Synthetic mode - Single generation
        print("Synthetic mode requested.")
        new_docs = SyntheticGenerator.generate_corpus(n_per_style=100)
        corpus.extend(new_docs)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(corpus, f, indent=2, ensure_ascii=False)
        print(f"Saved synthetic corpus to {args.output}")

    else:
        print("Using Unofficial JSON API (No Auth required).")
        fetcher = RedditJSONFetcher()
        fetcher.load_existing_ids(corpus)

        if args.interval > 0:
            print(
                f"Starting monitor mode. Press Ctrl+C to stop. Checking every {args.interval} minutes."
            )
            try:
                while True:
                    # Fetch batch (smaller limit for updates)
                    new_docs = fetcher.fetch_corpus(limit_per_sub=50)

                    if new_docs:
                        corpus.extend(new_docs)
                        # Save immediately so data isn't lost
                        with open(args.output, "w", encoding="utf-8") as f:
                            json.dump(corpus, f, indent=2, ensure_ascii=False)
                        print(
                            f"Saved updated corpus ({len(corpus)} total docs) to {args.output}"
                        )
                    else:
                        print("No new documents found this cycle.")

                    print(f"Sleeping for {args.interval} minutes...")
                    time.sleep(args.interval * 60)

            except KeyboardInterrupt:
                print("\n\nStopping monitor. Data is safe.")
                sys.exit(0)
        else:
            # Single run
            new_docs = fetcher.fetch_corpus(limit_per_sub=100)
            corpus.extend(new_docs)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(corpus, f, indent=2, ensure_ascii=False)
            print(f"Saved corpus to {args.output}")
