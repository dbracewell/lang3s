import sys

import numpy as np
import torch
from datasets import load_dataset
from scipy.stats import spearmanr
from sentence_transformers import SentenceTransformer
from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator
from sentence_transformers.readers.InputExample import InputExample

from lang3s.models.embedder import Embedder
from lang3s.models.layers.projection import SemanticProjectionHead  # your trained head

teacher_model_name: str = "sentence-transformers/all-mpnet-base-v2"


def load_sts_examples(split="test", lang="en"):
    ds = load_dataset("stsb_multi_mt", lang, split=split)
    examples = []

    for ex in ds:
        s1 = ex["sentence1"]
        s2 = ex["sentence2"]
        score = float(ex["similarity_score"])

        examples.append(InputExample(
            texts=[s1, s2],
            label=score / 5.0  # normalize 0–5 to 0–1
        ))
    return examples


def build_sts_evaluator(split="test", lang="en"):
    examples = load_sts_examples(split=split, lang=lang)
    return EmbeddingSimilarityEvaluator.from_input_examples(
        examples,
        name=f"sts_{lang}_{split}"
    )


def evaluate_sts(student_head_path, device="cpu"):
    evaluator = build_sts_evaluator(split="test", lang="en")

    class DummyModelCardData:
        def __init__(self):
            self.evaluation_data = []

        def set_evaluation_metrics(self, evaluator, metrics, epoch, step):
            self.evaluation_data.append({
                "evaluator": getattr(evaluator, "name", None),
                "metrics": metrics,
                "epoch": epoch,
                "step": step,
            })

    # Build wrapper to expose encode()
    class StudentWrapper:
        def __init__(self, embedder, head, device="cpu", use_projection=True):
            self.embedder = embedder
            self.head = head
            self.device = device

            # Required by EmbeddingSimilarityEvaluator
            self.similarity_fn_name = "cosine"
            self.model_card_data = DummyModelCardData()
            self.use_projection = use_projection

        def encode(self, sentences, *args, **kwargs):
            """
            Accepts arbitrary keyword args to maintain compatibility
            with SentenceTransformer.encode().
            """

            convert_to_numpy = kwargs.get("convert_to_numpy", True)
            normalize_embeddings = kwargs.get("normalize_embeddings", True)
            batch_size = kwargs.get("batch_size", 32)
            # (batch_size isn't used by your embedder)

            # Run your embedder
            res = self.embedder(sentences, is_split_into_words=False)

            # Projection head
            if self.use_projection:
                emb = self.head(
                    torch.tensor(np.array(res.sentence_embeddings), dtype=torch.float32, device=self.device)
                )
            else:
                emb = torch.tensor(np.array(res.sentence_embeddings), dtype=torch.float32, device=self.device)

            emb = emb.detach().cpu().numpy()

            if normalize_embeddings:
                emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8

            return emb

    teacher = SentenceTransformer(teacher_model_name, device=device)
    embedder = Embedder()
    embedder.device = device
    head = SemanticProjectionHead(embedder.dimensions, output_dim=768)
    head.load_state_dict(torch.load(student_head_path, map_location=device))
    head.eval()

    student = StudentWrapper(embedder, head)
    scores = evaluator(student)
    scores2 = evaluator(teacher)
    scores3 = evaluator(StudentWrapper(embedder, head, use_projection=False))
    print("STS Benchmark Score Teacher:", scores2)
    print("STS Benchmark Score XLM Roberta:", scores3)
    print("STS Benchmark Score Student:", scores)


def evaluate_similarity_alignment(student_head_path,
                                  teacher_model="sentence-transformers/all-mpnet-base-v2",
                                  sentences=None,
                                  device="cpu"):
    # Load teacher
    teacher = SentenceTransformer(teacher_model, device=device)

    # Load student
    embedder = Embedder()
    embedder.device = device
    head = SemanticProjectionHead(embedder.dimensions, output_dim=teacher.get_sentence_embedding_dimension())
    head.load_state_dict(torch.load(student_head_path, map_location=device))
    head.to(device)
    head.eval()

    # Prepare text
    if sentences is None:
        # small quick multilingual sample
        sentences = [
            "The cat sat on the mat.",
            "A dog is sleeping on a rug.",
            "The Eiffel Tower is in Paris.",
            "He is reading a newspaper.",
            "今日は寿司を食べました。",
            "明日は雨が降るでしょう。",
            "私は本を読みます。",
            "これはとても面白い映画です。",
            "This movie is very interesting.",
            "Machine learning models can learn representations.",
            "Embedding models are used for semantic search.",
        ]

    print("Computing teacher embeddings...")
    teacher_emb = teacher.encode(
        sentences,
        convert_to_numpy=True,
        normalize_embeddings=True,
        batch_size=64,
        show_progress_bar=False,
    )

    print("Computing student embeddings...")
    res = embedder(sentences, is_split_into_words=False)
    student_emb = head(
        torch.tensor(res.sentence_embeddings, dtype=torch.float32, device=device)
    ).cpu().detach().numpy()

    # similarity matrices
    teach_sim = teacher_emb @ teacher_emb.T
    stud_sim = student_emb @ student_emb.T

    # correlation
    rho, p = spearmanr(teach_sim.flatten(), stud_sim.flatten())

    print("====== Similarity Structure Alignment Test ======")
    print(f"Spearman correlation: {rho:.4f} (p={p})")
    print("=================================================")

    return rho


# evaluate_similarity_alignment("semantic_head_distilled_mpnet_multilingual.pt", device="cpu")
evaluate_sts(sys.argv[1])
