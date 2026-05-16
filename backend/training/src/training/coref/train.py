import os

import torch
import torch.nn.functional as F
from lang3s.data.filestore import FILE_STORE
from lang3s.models.coref_ranker import FastCorefRanker
from torch.optim import AdamW
from torch.optim.lr_scheduler import OneCycleLR
from tqdm import tqdm

from training.coref.coref_config import TRAINING_DATA_DIR
from training.coref.io import load_preprocessed_data

os.environ["TQDM_DISABLE"] = "0"


def train_coref_model(
    model,
    train_documents,
    val_documents=None,
    epochs=40,
    max_lr=1e-3,
    max_candidates=50,
    positive_weight=5.0,
):
    optimizer = AdamW(model.parameters(), lr=max_lr, weight_decay=0.01)
    total_steps = len(train_documents) * epochs
    scheduler = OneCycleLR(
        optimizer,
        max_lr=max_lr,
        total_steps=total_steps,
        pct_start=0.1,
    )

    model.train()

    for epoch in range(epochs):
        total_loss = 0.0

        for doc in tqdm(train_documents, desc=f"Epoch {epoch + 1}"):
            doc_losses = []

            for i, current_mention in enumerate(doc):
                if i == 0:
                    continue

                start_idx = max(0, i - max_candidates)
                candidates = doc[start_idx:i]
                distances = torch.tensor(
                    [min(i - (start_idx + j), 9) for j in range(len(candidates))]
                )

                scores = model(current_mention, candidates, distances)

                gold_indices = []
                current_cluster = current_mention.get("cluster_id")

                if current_cluster is None:
                    gold_indices.append(0)
                else:
                    for j, c in enumerate(candidates):
                        if c.get("cluster_id") == current_cluster:
                            gold_indices.append(j + 1)

                    if not gold_indices:
                        gold_indices.append(0)

                gold_indices_tensor = torch.tensor(gold_indices)
                loss = marginalized_nll_loss(scores, gold_indices_tensor)

                # If this mention actually links back to a previous entity
                # (meaning the gold indices aren't just the dummy [0]),
                # heavily penalize the model for getting it wrong.
                if gold_indices != [0]:
                    loss = loss * positive_weight

                doc_losses.append(loss)

            if doc_losses:
                total_doc_loss = torch.sum(torch.stack(doc_losses))

                optimizer.zero_grad()
                total_doc_loss.backward()

                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()

                total_loss += total_doc_loss.item()

        print(f"Epoch: {epoch + 1} Total Loss: {total_loss:.5f}", flush=True)

    return model


def save_coref_model(model, filepath):
    """
    Saves the model's weights and the architecture parameters needed to rebuild it.
    """
    checkpoint = {
        "embedding_dim": model.embedding_dim,
        "hidden_dim": model.hidden_dim,
        "max_distance_bins": model.max_distance_bins,
        "model_state_dict": model.state_dict(),
    }

    torch.save(checkpoint, filepath)
    print(f"Model successfully saved to {filepath}")


def marginalized_nll_loss(scores, gold_antecedent_indices):
    """
    scores: Tensor of shape (num_candidates + 1) -> [dummy_score, score_1, score_2...]
    gold_antecedent_indices: List or Tensor of indices for correct antecedents.
                             Index 0 is the dummy (meaning no coref).
    """
    log_probs = F.log_softmax(scores, dim=0)
    gold_log_probs = log_probs[gold_antecedent_indices]
    marginalized_log_prob = torch.logsumexp(gold_log_probs, dim=0)
    return -marginalized_log_prob


if __name__ == "__main__":
    training_data = load_preprocessed_data(filepath=TRAINING_DATA_DIR, device="cpu")
    trained_model = train_coref_model(FastCorefRanker(), training_data)
    path = FILE_STORE.get_file_path("models/coref-new.pt")
    save_coref_model(trained_model, path)
