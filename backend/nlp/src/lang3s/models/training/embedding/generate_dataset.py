import pickle

from torch.utils.data import Dataset
from tqdm import tqdm
from lang3s import config


class DistillationDataset(Dataset):
    def __init__(self, data_path):
        """
        Loads the precomputed (Text, Teacher_Embedding) pairs.
        """
        print(f"Loading precomputed data from {data_path}...")
        with open(data_path, "rb") as f:
            data = pickle.load(f)

        self.texts = data["texts"]
        self.embeddings = data["embeddings"]  # Tensor of shape [N, Hidden_Size]

        print(f"Loaded {len(self.texts)} training samples.")

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        # We return the RAW text because the Student needs to tokenize it
        # (potentially with dynamic padding during the collate_fn step)
        return {
            "text": self.texts[idx],
            "target_embedding": self.embeddings[idx]
        }


def prepare_distillation_data(
    raw_records,
    teacher_model,
    teacher_tokenizer,
    output_path="train_data.pkl",
    batch_size=32,
    device=config.TRAINING_DEVICE
):
    """
    1. Extracts unique sentences from Anchor/Pos/Neg triplets.
    2. Computes Teacher Embeddings.
    3. Saves to disk.
    """
    print("Extracting unique sentences from raw records...")
    unique_sentences = set()

    # Flatten the dataset: We don't care about triplets anymore, just diverse text.
    for record in raw_records:
        if "anchor" in record and record["anchor"]: unique_sentences.add(record["anchor"])
        if "positive" in record and record["positive"]: unique_sentences.add(record["positive"])
        if "negative" in record and record["negative"]: unique_sentences.add(record["negative"])

    sorted_sentences = sorted(list(unique_sentences))  # Sort for deterministic ordering
    print(f"Found {len(sorted_sentences)} unique sentences.")

    # --- Precompute Teacher Embeddings ---
    print("Precomputing Teacher Embeddings...")
    teacher_model.to(device)
    teacher_model.eval()

    all_embeddings = []

    # Process in batches
    with torch.no_grad():
        for i in tqdm(range(0, len(sorted_sentences), batch_size)):
            batch_texts = sorted_sentences[i: i + batch_size]

            # Tokenize
            inputs = teacher_tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt"
            ).to(device)

            # Teacher Forward Pass
            outputs = teacher_model(**inputs)

            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state

            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            batch_embeddings = sum_embeddings / sum_mask

            all_embeddings.append(batch_embeddings.cpu())

    # Concatenate all batches
    final_embeddings = torch.cat(all_embeddings, dim=0)

    # Save to disk
    payload = {
        "texts": sorted_sentences,
        "embeddings": final_embeddings
    }

    with open(output_path, "wb") as f:
        pickle.dump(payload, f)  # type:ignore

    print(f"Saved processed dataset to {output_path}")
    return output_path


def is_clean(text):
    if not isinstance(text, str) or len(text) < 5 or len(text) > 400:
        return False
    return True


if __name__ == "__main__":
    from transformers import AutoModel, AutoTokenizer
    from datasets import load_dataset
    import torch

    # --- CONFIGURATION ---
    # We use a multilingual teacher so it understands both your EN and JA data
    TEACHER_MODEL_ID = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    OUTPUT_FILE = "train_data.pkl"
    DEVICE = config.TRAINING_DEVICE

    print(f"--- Starting Data Preparation on {DEVICE} ---")

    # --- STEP 1: LOAD TEACHER ---
    print(f"Loading Teacher Model: {TEACHER_MODEL_ID}")
    teacher_tokenizer = AutoTokenizer.from_pretrained(TEACHER_MODEL_ID)
    teacher_model = AutoModel.from_pretrained(TEACHER_MODEL_ID)
    teacher_model.to(DEVICE)

    # --- STEP 2: LOAD & MERGE DATASETS ---
    raw_records = []

    # A. Load Parallel Talks (English-Japanese)
    print("Loading Parallel Data (Talks)...")
    try:
        ds_talks = load_dataset("sentence-transformers/parallel-sentences-talks", "en-ja", split="train")
        for row in ds_talks:
            raw_records.append({
                "anchor": row.get('english', ''),
                "positive": row.get('non_english', ''),
                "negative": None
            })
        print(f"Added {len(ds_talks)} samples from Talks.")
    except Exception as e:
        print(f"Warning: Could not load Talks data. {e}")

    # B. Load NLI Data (Triplets)
    print("Loading NLI Data...")
    try:
        ds_nli = load_dataset("sentence-transformers/all-nli", "triplet", split="train")
        for row in ds_nli:
            raw_records.append({
                "anchor": row.get('anchor', ''),
                "positive": row.get('positive', ''),
                "negative": row.get('negative', '')
            })
        print(f"Added {len(ds_nli)} samples from NLI.")
    except Exception as e:
        print(f"Warning: Could not load NLI data. {e}")

    print("Loading MS MARCO (Search Data)...")
    try:
        ds_marco = load_dataset("sentence-transformers/embedding-training-data", "msmarco-triplet",
                                split="train[:150000]")

        for row in ds_marco:
            raw_records.append({
                "anchor": row['query'],  # type: ignore
                "positive": row['positive'],  # type:ignore
                "negative": row['negative']  # type: ignore
            })
        print(f"Added {len(ds_marco)} samples from MS MARCO.")
    except Exception as e:
        print(f"Warning: Could not load MS MARCO. {e}")

    print(f"Total Raw Records: {len(raw_records)}")

    # --- STEP 3: RUN GENERATION ---
    # This will:
    # 1. Extract unique sentences from all 'anchor', 'positive', 'negative' fields
    # 2. Compute Teacher Embeddings for every unique sentence
    # 3. Save to disk
    prepare_distillation_data(
        raw_records=raw_records,
        teacher_model=teacher_model,
        teacher_tokenizer=teacher_tokenizer,
        output_path=OUTPUT_FILE,
        batch_size=32,  # Increase to 64 or 128 if you have >16GB VRAM
        device=DEVICE
    )

    print("\n✅ Data Preparation Complete.")
