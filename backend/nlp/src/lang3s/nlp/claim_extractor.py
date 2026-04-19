from __future__ import annotations

import os.path
import re

import torch
from pydantic import BaseModel
from torch.cuda import temperature
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from lang3s import config
from lang3s.data.db.models import ClaimsTable


class ClaimExample(BaseModel):
    claim: str
    source: str | None = None


class DocumentClaims(BaseModel):
    claims: list[ClaimExample]


class DocumentClaimRequest(BaseModel):
    documentId: str
    text: str


class SentenceContext(BaseModel):
    sentenceAid: str
    text: str


class DocumentClaimContext(BaseModel):
    documentId: str
    sentences: list[SentenceContext]


class ClaimExtractor:
    def __init__(self, batch_size=64):
        model_name = os.path.join(config.MODELS_DIR, "t5_finetuned_model")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name, torch_dtype="bfloat16"
        ).to("mps")
        self.batch_size = batch_size

    def process(self, request: DocumentClaimContext):
        raw_sentences = [s.text for s in request.sentences]
        prompts = []
        for i in range(len(raw_sentences)):
            prompt = f"{' '.join(raw_sentences[i - 2 : i])} {raw_sentences[i]}"
            prompts.append(prompt)
        total_tokens = 0
        extracted_claims: list[ClaimsTable] = []

        for i in range(0, len(prompts), self.batch_size):
            batch = prompts[i : i + self.batch_size]
            inputs = self.tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                max_length=2048,
                truncation=True,
            ).to("mps")
            total_tokens += torch.sum(inputs["attention_mask"]).detach().item()
            with torch.inference_mode():
                output_sequences = self.model.generate(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                    max_new_tokens=2048,
                    temperature=0,
                    return_dict_in_generate=True,
                    output_scores=True,
                )
            transition_scores = self.model.compute_transition_scores(
                output_sequences.sequences,
                output_sequences.scores,
                normalize_logits=True,
            )
            output_text = self.tokenizer.batch_decode(
                output_sequences.sequences, skip_special_tokens=True
            )
            for i, sentence in enumerate(request.sentences[i : i + self.batch_size]):
                output_length = 1e-6 + (transition_scores[i] != 0).sum()
                sum_log_probs = transition_scores[i].sum()
                mean_log_prob = sum_log_probs / output_length
                perplexity = torch.exp(-mean_log_prob).item()
                if perplexity < 1.5:
                    generated_text = output_text[i]
                    match = re.search(
                        r"claim:\s*(.*?)\s*source:\s*(.*)",
                        generated_text,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if match:
                        claim = match.group(1).strip()
                        source = match.group(2).strip()
                        if claim.lower() == "no claim":
                            continue
                        extracted_claims.append(
                            ClaimsTable(
                                documentId=request.documentId,
                                claim=claim,
                                source=source,
                            )
                        )
                del output_length
                del sum_log_probs
                del mean_log_prob
                del perplexity
            del inputs
            del transition_scores

        del prompts
        torch.mps.empty_cache()

        return {"tokens": total_tokens, "claims": extracted_claims}
