import numpy as np
import torch
from datasets import load_dataset
from scipy.stats import spearmanr
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from lang3s import config
from lang3s.models.embedder import Embedder

# --- 1. CONFIGURATION ---
# Path to your trained head
MODEL_PATH = "xlmr_to_mpnet_projection_head_v3.pth"
BATCH_SIZE = 32
TEACHER_ID = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> np.ndarray:
    """Computes cosine similarity between two batches of embeddings."""
    norm1 = np.linalg.norm(emb1, axis=1)
    norm2 = np.linalg.norm(emb2, axis=1)
    dot_product = (emb1 * emb2).sum(axis=1)
    return dot_product / (norm1 * norm2 + 1e-9)


def main():
    device = config.TRAINING_DEVICE

    # A. Initialize Your Custom Backbone
    print("Initializing your Custom Embedder...")
    # The Embedder handles its own config/device/model loading
    backbone = Embedder()

    teacher_model = SentenceTransformer(TEACHER_ID).to(device)
    teacher_model.eval()

    compress_layer = torch.nn.Linear(768, 384)
    compress_layer.load_state_dict(torch.load("./finetuned_xlm_roberta/compressed.pt"))
    compress_layer.to(device)
    # C. Load STSB Dataset
    print("Loading STSB Validation Set...")
    dataset = load_dataset("sentence-transformers/stsb", split="test")
    # dataset = load_sts_examples("test")
    sentences1 = dataset["sentence1"]
    sentences2 = dataset["sentence2"]
    gold_scores = dataset["score"]

    # D. Inference Loop
    print(f"Evaluating on {len(gold_scores)} pairs...")

    def get_vectors(text_list):
        t_batch = teacher_model.encode(text_list, show_progress_bar=False)
        result = backbone(text_list, batch_size=BATCH_SIZE)
        vecs_torch = torch.as_tensor(
            np.array(result.sentence_embeddings), device=device
        )
        # with torch.no_grad():
        #     vecs_np = compress_layer(vecs_torch).cpu().numpy()
        vecs_np = vecs_torch.detach().cpu().numpy()
        return vecs_np, t_batch

    # Run Inference in Batches
    all_cosine_scores = []
    xlm_cosine_scores = []
    teacher_cosine_scores = []

    for i in tqdm(range(0, len(sentences1), BATCH_SIZE)):
        batch_s1 = sentences1[i : i + BATCH_SIZE]  # type:ignore
        batch_s2 = sentences2[i : i + BATCH_SIZE]  # type:ignore

        # Get Projected Vectors
        xlm1, temb1 = get_vectors(batch_s1)
        xlm2, temb2 = get_vectors(batch_s2)

        # Compute Cosine Similarity
        xlm_cosine_scores.extend(cosine_similarity(xlm1, xlm2).tolist())
        teacher_cosine_scores.extend(cosine_similarity(temb1, temb2).tolist())

    # E. Calculate Spearman
    xlm_spearman_corr, _ = spearmanr(gold_scores, xlm_cosine_scores)
    teacher_spearman_corr, _ = spearmanr(gold_scores, teacher_cosine_scores)

    print("\n" + "=" * 40)
    print(
        f"✅ Corrected STSB Fine Tuned XLM Roberta Spearman Correlation: {xlm_spearman_corr * 100:.2f}"
    )
    print(
        f"✅ Corrected STSB Teacher Spearman Correlation: {teacher_spearman_corr * 100:.2f}"
    )
    print("=" * 40)


if __name__ == "__main__":
    main()
