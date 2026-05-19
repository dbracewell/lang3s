import json
import random
import time
from typing import Any, List

import spacy
from pydantic import BaseModel
from tqdm import tqdm

from lang3s.data.filestore import FILE_STORE
from lang3s.llm import ChatModel

OUTPUT_FILE = FILE_STORE.get_file_path("slang_training_data.jsonl")
NUM_BATCHES_TO_GENERATE = 1500

nlp = spacy.load("en_core_web_lg")


TOPICS = [
    "a difficult breakup",
    "playing a video game with bugs",
    "a funny encounter at a grocery store",
    "complaining about a boss",
    "asking for relationship advice",
    "reviewing a mediocre movie",
    "studying for a difficult exam",
    "losing keys",
    "cooking a meal that went wrong",
    "traffic during rush hour",
    "asking for relationship advice",
    "a difficult breakup",
    "traffic during rush hour",
    "looking for workout motivation",
    "dealing with a sudden job loss",
    "planning a surprise birthday party",
    "searching for affordable housing options",
    "advice on buying your first car",
    "how to improve public speaking skills",
    "sharing favorite vegan recipes",
    "discussing the latest smartphone release",
    "debating climate change policies",
    "recommendations for indie video games",
    "tips for traveling on a budget",
    "exploring side‑business ideas",
    "navigating mental health challenges",
    "looking for book club suggestions",
    "planning a weekend getaway",
    "questions about cryptocurrency investing",
    "sharing DIY home improvement hacks",
    "finding support after losing a pet",
    "advice on choosing college majors",
    "tips for learning a new language",
    "debate over the best streaming service",
    "help with preparing for an interview",
    "sharing funny office anecdotes",
    "looking for pet adoption stories",
    "discussing the latest political news",
    "requests for parenting hacks",
    "exploring sustainable fashion choices",
    "tips for effective time management",
    "searching for local volunteer opportunities",
    "sharing travel photography tips",
    "questions about home schooling methods",
    "debate over best music streaming platforms",
    "advice on dealing with chronic pain",
    "looking for movie recommendations",
    "discussing mental health apps",
    "sharing plant‑care advice for beginners",
    "requests for healthy snack ideas",
    "questions about tax filing online",
    "planning a backyard garden",
    "debate over best productivity tools",
    "looking for workout playlists",
    "advice on choosing insurance plans",
    "sharing creative writing prompts",
    "questions about remote work setups",
    "discussing the latest fashion trends",
    "requests for healthy meal prep ideas",
    "looking for ways to reduce screen time",
]

SUBCULTURES = [
    "Gen Z / Zoomer",
    "Gen X",
    "Baby Boomer",
    "Midwestern Mom",
    "Corporate Professional / Tech Bro",
    "Hardcore Gamer / Twitch Streamer",
    "Hip Hop / Street Culture",
    "British / UK Drill",
    "Australian",
    "Soccer / Football Fan",
    "Stan Twitter (Fandoms)",
    "Gym Bro",
    "Fashionistas",
    "Southern Pride",
    "Republican",
    "Democrat",
    "MAGA",
    "Libertarian",
    "Christian",
    "Atheist",
    "Muslim",
]

SUBCULTURES_INFO = {
    "Gen Z / Zoomer": "Young internet-native generation using terms like 'no cap', 'bet', 'rizz', 'finna', 'ghosting', 'vibes'.",
    "Gen X": "The generation known for grunge, irony, and terms like 'whatever', 'dude', 'psych', 'rad', 'totally'.",
    "Baby Boomer": "Older generation using traditional idioms or dated slang like 'groovy', 'far out', 'bummer', 'knuckle sandwich'.",
    "Midwestern Mom": "Polite, folksy American Midwest dialect using 'ope', 'you betcha', 'pop', 'jeepers', 'for pete's sake'.",
    "Corporate Professional / Tech Bro": "Business jargon and tech-speak like 'circle back', 'synergy', 'bandwidth', 'disrupt', 'unicorn', 'touch base'.",
    "Hardcore Gamer / Twitch Streamer": "Video game and streaming terminology like 'pog', 'nerf', 'buff', 'GG', 'noob', 'clutch', 'inting'.",
    "Hip Hop / Street Culture": "Urban African American Vernacular English (AAVE) influences like 'drip', 'fam', 'opp', 'flex', 'guap'.",
    "British / UK Drill": "UK-specific slang like 'innit', 'bruv', 'mandem', 'peng', 'roadman', 'wasteman'.",
    "Australian": "Australian English slang like 'arvo', 'brekkie', 'mate', 'stoked', 'bogan', 'servo'.",
    "Soccer / Football Fan": "Sports terminology like 'nutmeg', 'clean sheet', 'park the bus', 'gola', 'absolute sitter'.",
    "Stan Twitter (Fandoms)": "Obsessive fan culture terms like 'stan', 'ship', 'cancel', 'tea', 'wig', 'slay'.",
    "Gym Bro": "Fitness culture slang like 'gains', 'swole', 'pr', 'cut', 'bulk', 'natty', 'do you even lift'.",
    "Cottagecore": "Romanticized rural life aesthetic slang like 'pastel fields', 'flowy dresses', 'woodland fairies'.",
    "Y2K Nostalgia": "Revival of early-2000s slang like 'croptop', 'low rise jeans', 'MP3 player', 'slutty shirt'.",
    "Crypto / NFT Enthusiast": "Cryptocurrency-related jargon like 'HODL', 'bagholder', 'meme stock', 'diamond hands'.",
    "Anime / Otaku Culture": "Terms from Japanese animation fandom like 'waifu', 'bias change', 'senpai', 'headcanon'.",
    "Podcast / True Crime Fan": "True crime community slang like 'cold case', 'deep dive', 'red herring', 'episode binge'.",
    "Dog Person": "Canine-loving community slang like 'floof', 'snoot wipe', 'treat pouch', 'doggo'.",
    "Stock Market Day Trader": "Day trading slang influenced by Reddit culture like 'GameStop moment', 'meme stock', 'buy the dip'.",
    "Yoga / Wellness Culture": "Mindfulness-focused terms like 'glow up', 'detox', 'self-care ritual', 'third eye'.",
    "Progressive Activism/Anti-Racism Advocates": "Terms like 'call out culture', 'intersectional', 'allyship', 'privilege check', 'systemic racism', 'woke' dominate discussions.",
    "Republican/Conservative Commentariat": "Fox News-influenced slang such as 'woke mob', 'Cancel Culture', 'Liberal Media', 'pull up a chair', 'red wave' reflects political discourse.",
    "QAnon Conspiracy Theorists": "Uses phrases like 'Deep State', 'MK Ultra', 'pedo ring', 'Truthers', 'The Storm' to describe speculative narratives.",
    "Libertarian/Anarcho-Capitalists": "Advocates freedom-centric language like 'voluntaryism', 'zero tolerance', 'skin-in-the-game', 'state violence', 'privateers'.",
    "Evangelical/Christian Fundamentalist": "Includes Bible-centric slang like 'devo', 'WWJD?', 'faith walk', 'born again', 'cult watch' discussions.",
    "Marxist/Labor Organizer": "Terms like 'solidarity', 'capitalism critique', 'surplus value', 'rent extraction', 'union-busting' define political economy discussions.",
    "Anti-Vaccine (Anti-Vaxxer)": "Uses phrases like 'natural immunity', 'big pharma', 'medical tyranny', 'herd mentality', 'toxic jab' during health debates.",
    "Environmental/Climate Activist": "Focuses on terms like 'climate grief', 'greenwashing', 'carbon insetting', 'blockadia', 'extinction rebellion'.",
    "Islamophobic (Muslim-Phobic) Rhetoric": "Incorporates terms like 'ISIS cult', 'terrorist flag', 'no-sharia laws', 'halal meat terrorism' in discriminatory speech.",
    "Islam and Muslim Communities": "Blends Islamic Arabic terms like 'Insha’Allah', 'JazakAllahu Khairan', and phrases like 'halal-friendly' with modern adaptations.",
    "Transhumanist/Futurist": "Discusses concepts like 'singularity', 'neural lace', 'post-humanism', 'upload consciousness', 'death transcendence'.",
    "Secular/Atheist Humanist": "Uses terms like 'God of the gaps', 'moral without religion', 'naturalistic ethics', 'New Atheism' debates.",
    "Neo-Liberal/Free Market Laissez-Faire": "Advocates deregulation language like 'hands-off policy', 'market solutions', 'entrepreneur state', 'free trade zones'.",
    "Anti-Government/Prepper": "Terms like 'boondocks retreat', 'bug out bag', 'preparedness', 'government collapse', 'no-trust' mindset.",
    "Hindu-American/Deshi Culture": "Blends Hindu terms like 'namaste', 'satsang', 'karma yoga' with modern descriptors like 'diwali party', 'chutney music'.",
    "Jewish-American (Modern Orthodox)": "Uses Hebrew/Aramaic phrases like 'bris', 'challah', 'tzitzit' alongside secular lingo like 'Shabbos queen', 'kosher TikTok'.",
    "Black Nationalist (Afrocentric)": "Phrases like 'keep it real', 'black is beautiful', 'Pan-Africanism', 'Marcus Garvey' resonate in cultural narratives.",
    "Anti-Immigrant/Border Hardliner": "Terms like 'build that wall', 'anchor babies', 'chain migration', 'border security' dominate political rhetoric.",
    "Crypto-Anarchist/Sovereign Individual": "Fuses libertarianism with crypto jargon like 'decentralize power', 'self-sovereign identity', 'digital nomad taxes'.",
    "Mormon/Church of Jesus Christ of Latter-day Saints": "Uses LDS-specific terms like 'family home evening', 'fast Sunday', 'temple recommend', 'word of wisdom'.",
}


class ExampleList(BaseModel):
    standard_english_examples: List[str]
    slang_and_idioms_examples: List[str]
    slang_and_idioms_used: List[str]


class LocalLLMGenerator:
    def __init__(self):
        self.model = ChatModel("openai/gpt-oss-20b")

    def generate(self, topic: str, subculture: str, description: str) -> ExampleList:
        response = self.model.chat(
            messages=[
                {
                    "role": "user",
                    "content": f"""
        You are a dataset generator for a slang detection AI.
        Generate a JSON object containing sentences about the topic: "{topic}".
        
        Context for Subculture ({subculture}): {description}
        
        Requirements:
        1. "standard_english_examples": 5 sentences using strictly formal, textbook English. No slang, no idioms.
        2. "slang_and_idioms_examples": 5 sentences using specific slang, uncommon abbreviations, acronyms, idioms, or colloquialisms typical of a {subculture}
        3. "slang_and_idioms_used": A list of the specific slang phrases or idioms used in the examples above.
           IMPORTANT: Do NOT list standard adjectives (like "ambitious", "bold", "good") unless they are specific slang for this group.
           Output all text in plain text, no markdown
           
           /no_think
        """,
                }
            ],
            temperature=0.7,
            response_model=ExampleList,
        )
        return response.parsed


def find_sublist(slang_tokens, sentence_tokens):
    """
    Finds the start index of slang_tokens inside sentence_tokens.
    Returns -1 if not found.
    """
    slang_len = len(slang_tokens)
    sent_len = len(sentence_tokens)

    for i in range(sent_len - slang_len + 1):
        if sentence_tokens[i : i + slang_len] == slang_tokens:
            return i
    return -1


def process_batch(data: ExampleList) -> List[dict[str, Any]]:
    processed_examples = []

    for text in data.standard_english_examples:
        doc = nlp(text)
        tokens = [t.text for t in doc]
        labels = [0] * len(tokens)
        processed_examples.append(
            {
                "tokens": tokens,
                "ner_tags": labels,
                "original_text": text,
                "type": "standard",
            }
        )

    slang_terms = data.slang_and_idioms_used
    processed_slang_terms = []
    for term in slang_terms:
        term_doc = nlp(term)
        processed_slang_terms.append([t.text.lower() for t in term_doc])

    for text in data.slang_and_idioms_examples:
        doc = nlp(text)
        tokens = [t.text for t in doc]
        tokens_lower = [t.lower() for t in tokens]
        labels = [0] * len(tokens)

        found_slang = False

        for term_tokens in processed_slang_terms:
            start_idx = find_sublist(term_tokens, tokens_lower)
            if start_idx != -1:
                labels[start_idx] = 1  # B-SLANG
                for i in range(start_idx + 1, start_idx + len(term_tokens)):
                    labels[i] = 2  # I-SLANG
                found_slang = True

        if found_slang:
            processed_examples.append(
                {
                    "tokens": tokens,
                    "ner_tags": labels,
                    "original_text": text,
                    "type": "slang",
                }
            )

    return processed_examples


def main():
    generator = LocalLLMGenerator()
    all_training_data = []

    print(f"Starting generation for {NUM_BATCHES_TO_GENERATE} batches...")
    selected_topics = random.choices(TOPICS, k=NUM_BATCHES_TO_GENERATE)
    subculture_keys = list(SUBCULTURES_INFO.keys())
    selected_subcultures = random.choices(subculture_keys, k=NUM_BATCHES_TO_GENERATE)

    for topic, subculture in tqdm(zip(selected_topics, selected_subcultures)):
        examples = generator.generate(topic, subculture, SUBCULTURES_INFO[subculture])
        try:
            processed_examples = process_batch(examples)
            for e in processed_examples:
                if e["type"] == "slang":
                    print(topic, subculture)
                    print(e["original_text"])
                    print(e["ner_tags"])
            all_training_data.extend(processed_examples)
        except Exception as e:
            print(f"Error processing batch for '{topic}': {e}")
        time.sleep(2)

    print(f"Saving {len(all_training_data)} examples to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in all_training_data:
            f.write(json.dumps(entry) + "\n")

    print("Done. You can now run 'train_slang_detector.py' pointing to this file.")


if __name__ == "__main__":
    main()
