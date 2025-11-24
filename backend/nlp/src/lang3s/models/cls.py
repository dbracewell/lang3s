import torch
import torch.nn.functional as F


class ClsDetector:
    """
    Universal sentence embedding extractor for HuggingFace models.

    Handles:
      • Encoder-only models (BERT, RoBERTa, DeBERTa, XLM-R…)
      • Decoder-only LLMs (LLaMA, Mistral, GPT-J…)
      • Seq2Seq encoders (T5, Flan-T5, BART…)
    """

    def __init__(self, tokenizer, model):
        self.tokenizer = tokenizer
        self.model = model
        self.model_type = self.detect_model_type()
        self.cls_token, self.cls_id = self.detect_cls_token()

    # -------------------------------------------------------------------------
    # 1) Detect Model Type
    # -------------------------------------------------------------------------
    def detect_model_type(self):
        config = self.model.config

        if hasattr(config, "is_decoder") and config.is_decoder:
            return "decoder"

        # T5/BART etc. have is_decoder=False for the encoder
        if config.__class__.__name__.lower().startswith(("t5", "bart")):
            return "seq2seq-encoder"

        return "encoder"

    # -------------------------------------------------------------------------
    # 2) Detect CLS Token (if applicable)
    # -------------------------------------------------------------------------
    def detect_cls_token(self):
        tok = self.tokenizer

        # Standard CLS token
        if tok.cls_token is not None:
            return tok.cls_token, tok.cls_token_id

        # RoBERTa/XLM-R/DeBERTa use <s> as CLS
        if tok.bos_token is not None:
            return tok.bos_token, tok.bos_token_id

        # Decoder-only models have no CLS
        return None, None

    def get_cls_embedding(self, batch, hidden):
        if self.model_type == "encoder":
            return self._from_encoder(hidden, batch)

        elif self.model_type == "decoder":
            return self._from_decoder(hidden, batch)

        elif self.model_type == "seq2seq-encoder":
            return self._from_encoder(hidden, batch)

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    # -------------------------------------------------------------------------
    # 5) Extractor Implementations
    # -------------------------------------------------------------------------
    def _from_encoder(self, hidden, batch):
        """
        Encoder-only models (BERT, RoBERTa, DeBERTa, XLM-R…)
        Strategy:
          1. Use CLS if available
          2. Otherwise BOS
          3. Otherwise mean pooling
        """
        if self.cls_id is not None:
            return hidden[:, 0, :]

        attention_mask = batch["attention_mask"].unsqueeze(-1)
        return (hidden * attention_mask).sum(dim=1) / attention_mask.sum(dim=1)

    def _from_decoder(self, hidden, batch):
        """
        Decoder-only models (LLaMA, GPT-J, Mistral…)
        Strategy:
          • Use last token embedding (standard CLS for LLMs)
          • Or attention-masked last non-pad token
        """
        attention_mask = batch["attention_mask"]
        lengths = attention_mask.sum(dim=1) - 1  # last real token index

        batch_embeddings = []
        for i, idx in enumerate(lengths):
            batch_embeddings.append(hidden[i, idx, :])

        return torch.stack(batch_embeddings, dim=0)

    # -------------------------------------------------------------------------
    # Utility: L2 Normalize
    # -------------------------------------------------------------------------
    def normalize(self, emb):
        return F.normalize(emb, p=2, dim=-1)
