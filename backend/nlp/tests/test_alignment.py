import torch


#
# These helpers simulate the behavior of your prepare_batch() and decoding
# but in a controlled environment with known expectations.
#

def simulate_embedded_subwords(tokens):
    """
    Simulate subword tokenization:
    - Each word splits into len(word) subwords for testing.
    - word_ids gives mapping from subwords → word index.
    """
    token_embeddings = []
    word_ids = []

    # Simulated H dimension
    H = 5

    for word_idx, tok in enumerate(tokens):
        n_sub = max(1, len(tok) // 3)  # predictable fake split
        for _ in range(n_sub):
            token_embeddings.append(torch.randn(H))
            word_ids.append(word_idx)

    return torch.stack(token_embeddings), word_ids


def prepare_batch_for_test(example):
    """
    Exactly mirrors your final prepare_batch logic, but using the simulated
    tokenizer above.
    """
    sentences = [example["tokens"]]
    gold_labels = [example["labels"]]

    token_embeddings_list = []
    word_ids_list = []
    lengths = []

    # Simulate embedder output
    for toks in sentences:
        emb, wids = simulate_embedded_subwords(toks)
        token_embeddings_list.append(emb)
        word_ids_list.append(wids)
        lengths.append(emb.shape[0])

    B = 1
    max_T = lengths[0]
    H = token_embeddings_list[0].shape[1]

    embeddings = torch.zeros((B, max_T, H))
    mask = torch.zeros((B, max_T), dtype=torch.bool)

    # Fill tensors
    embeddings[0, :lengths[0]] = token_embeddings_list[0]
    mask[0, :lengths[0]] = True

    # Word IDs (pad if needed)
    word_ids_padded = []
    wids = word_ids_list[0]
    padded = wids + [None] * (max_T - len(wids))
    word_ids_padded.append(padded)

    # Build word_to_subword
    word_to_subword = []
    wts = []
    for word_idx in range(len(gold_labels[0])):
        sub_positions = [i for i, w in enumerate(wids) if w == word_idx]
        if len(sub_positions) == 0:
            wts.append(None)
        else:
            wts.append(sub_positions[0])
    word_to_subword.append(wts)

    # Build aligned labels
    aligned = torch.full((B, max_T), fill_value=-100, dtype=torch.long)
    prev_word = None
    for sub_idx, wid in enumerate(padded):
        if wid is None:
            continue
        if wid != prev_word:
            aligned[0, sub_idx] = example["label2idx"][gold_labels[0][wid]]
        prev_word = wid

    return {
        "embeddings": embeddings,
        "labels": aligned,
        "mask": mask,
        "word_ids": word_ids_padded,
        "word_to_subword": word_to_subword,
        "orig_lengths": lengths,
        "gold_word_labels": gold_labels[0],
        "tokens": sentences[0],
    }


def decode_predictions(full_pred, word_to_subword, idx2label):
    """Mirror your decoding logic exactly."""
    pred_word_tags = []
    for sub_idx in word_to_subword[0]:
        if sub_idx is None:
            pred_word_tags.append("O")
        else:
            pred_word_tags.append(idx2label[full_pred[sub_idx].item()])
    return pred_word_tags


#
# -----------------------
# TESTS BEGIN HERE
# -----------------------
#

def test_alignment_first_subword_labeling():
    """
    Verify that alignment labels only first subword of each word.
    """
    example = {
        "tokens": ["The", "quick", "brown", "fox"],
        "labels": ["B-NP", "I-NP", "I-NP", "I-NP"],
        "label2idx": {"B-NP": 0, "I-NP": 1, "O": 2},
    }

    batch = prepare_batch_for_test(example)
    aligned = batch["labels"][0]  # (T,)
    wts = batch["word_to_subword"][0]

    for word_idx, sub_idx in enumerate(wts):
        assert aligned[sub_idx].item() == example["label2idx"][example["labels"][word_idx]]

    # All other positions must be -100
    for i in range(aligned.shape[0]):
        if i not in wts:
            assert aligned[i].item() == -100


def test_word_to_subword_mapping():
    """
    word_to_subword must map each word index to the subword index correctly.
    """
    example = {
        "tokens": ["Alaska", "is", "big"],
        "labels": ["B-NP", "B-VP", "B-ADJP"],
        "label2idx": {"B-NP": 0, "B-VP": 1, "B-ADJP": 2, "O": 3},
    }
    batch = prepare_batch_for_test(example)
    wts = batch["word_to_subword"][0]

    # Ensure mapping matches actual simulated subword positions
    _, wids = simulate_embedded_subwords(example["tokens"])
    expected = []
    for widx in range(len(example["tokens"])):
        positions = [i for i, w in enumerate(wids) if w == widx]
        expected.append(positions[0])

    assert wts == expected


def test_decode_roundtrip_identity():
    """
    Given aligned labels → logits that reproduce them → decoding
    must give identical word-level labels.
    """
    example = {
        "tokens": ["Updating", "alignment", "test"],
        "labels": ["B-NP", "I-NP", "I-NP"],
        "label2idx": {"B-NP": 0, "I-NP": 1, "O": 2},
    }
    idx2label = {v: k for k, v in example["label2idx"].items()}

    batch = prepare_batch_for_test(example)
    wts = batch["word_to_subword"][0]

    # Build fake logits that exactly predict the aligned labels
    aligned = batch["labels"][0]  # (T,)
    num_labels = len(example["label2idx"])
    T = aligned.shape[0]

    logits = torch.randn(T, num_labels) * 0.01  # small noise
    for i in range(T):
        if aligned[i] != -100:
            label_id = aligned[i].item()
            logits[i, :] = -10
            logits[i, label_id] = 10  # force argmax

    preds = logits.argmax(dim=-1)  # (T,)

    decoded = decode_predictions(preds, batch["word_to_subword"], idx2label)
    assert decoded == example["labels"]


def test_no_misalignment_after_padding():
    """
    If padding is introduced (simulated by shorter words), mapping must still match.
    """
    example = {
        "tokens": ["I", "love", "NY"],
        "labels": ["O", "B-VP", "B-NP"],
        "label2idx": {"O": 0, "B-VP": 1, "B-NP": 2},
    }
    batch = prepare_batch_for_test(example)
    wts = batch["word_to_subword"][0]
    # All indices must be < original T_b
    for sub in wts:
        if sub is not None:
            assert sub < batch["orig_lengths"][0]
