import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoConfig


# --- 1. DoRA Linear Layer Implementation ---
class DoRALinear(nn.Module):
    """
    A LoRA-based layer with Weight Decomposition (DoRA) applied to a frozen nn.Linear layer.
    """

    def __init__(self, original_layer: nn.Linear, rank: int = 8, alpha: int = 16):
        super().__init__()

        # 1. Freeze Original Weights (W_0)
        self.original_weight = original_layer.weight.data
        self.original_weight.requires_grad = False
        self.bias = original_layer.bias

        self.in_features = original_layer.in_features
        self.out_features = original_layer.out_features

        # 2. LoRA Components (Directional Update)
        self.lora_A = nn.Parameter(torch.empty(rank, self.in_features))
        self.lora_B = nn.Parameter(torch.empty(self.out_features, rank))
        self.scaling = alpha / rank

        # 3. DoRA Magnitude Component (Trainable Vector)
        # Initialize magnitude vector 'm' to the L2 norm of the original weight's rows
        self.m = nn.Parameter(
            torch.linalg.norm(self.original_weight, dim=1, keepdim=True)
        )

        self.reset_parameters()

    def reset_parameters(self):
        # Initialize W_A (Kaiming Uniform)
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        # Initialize W_B (Zeros - Crucial for starting from W_0)
        nn.init.zeros_(self.lora_B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # a) Compute the LoRA update matrix (Delta W = W_B @ W_A)
        delta_W = (self.lora_B @ self.lora_A) * self.scaling

        # b) Compute the Adapted Directional Weight (W_dir = W_0 + Delta W)
        W_dir = self.original_weight + delta_W

        # c) Compute the Current Magnitude (Current_m = ||W_dir||_2)
        # torch.linalg.norm is preferred for clarity
        W_dir_norm = torch.linalg.norm(W_dir, dim=1, keepdim=True)

        # d) Compute the Final DoRA Weight (W_DoRA = m * (W_dir / Current_m))
        # This replaces the magnitude of W_dir with the trainable magnitude 'm'
        W_DoRA = self.m * (W_dir / W_dir_norm)

        # e) Perform the linear transformation
        return F.linear(x, W_DoRA, self.bias)


# --- 2. Model Wrapper for DoRA Injection ---
class DoRASentenceModel(nn.Module):
    def __init__(self, model_name: str, rank: int = 8, alpha: int = 16):
        super().__init__()

        self.model_name = model_name
        self.rank = rank
        self.alpha = alpha

        # 1. Load the Base Transformer Model
        self.base_model = AutoModel.from_pretrained(model_name)

        # 2. Freeze all Base Model parameters
        for param in self.base_model.parameters():
            param.requires_grad = False

        # 3. Inject DoRA into the Attention and FFN linear layers
        self._inject_dora_layers()

        # 4. Add a simple token classification head (trainable)
        config = AutoConfig.from_pretrained(model_name)
        hidden_size = config.hidden_size
        NUM_TOKEN_CLASSES = 10  # Example number of token labels (e.g., NER tags)

        # This linear layer and its weights ARE TRAINABLE
        self.token_classifier = nn.Linear(hidden_size, NUM_TOKEN_CLASSES)

        print(
            f"DoRA Model Initialized. Trainable Params: {sum(p.numel() for p in self.parameters() if p.requires_grad)}")

    def _inject_dora_layers(self):
        """
        Recursively finds target nn.Linear layers and replaces them with DoRALinear.
        """
        target_names = ["query", "value", "key", "dense"]  # Common target matrices in attention/FFN

        for name, module in self.base_model.named_modules():
            # Check if the module is a Transformer layer's attention or FFN block
            if any(target in name for target in target_names) and isinstance(module, nn.Linear):
                # Replace the original nn.Linear layer with DoRALinear
                parent_name, attr_name = name.rsplit('.', 1)
                parent_module = self.base_model.get_submodule(parent_name)

                new_dora_layer = DoRALinear(
                    original_layer=module,
                    rank=self.rank,
                    alpha=self.alpha
                )

                # Assign the new layer back to the parent module
                setattr(parent_module, attr_name, new_dora_layer)

    def forward(self, input_ids, attention_mask=None, token_type_ids=None, task='sentence_similarity'):
        """
        Performs a forward pass and returns the output based on the specified task.
        """
        # Forward pass through the (DoRA-adapted) base model
        outputs = self.base_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=True
        )

        # The full token-level embeddings (B, L, H)
        full_token_embeddings = outputs.last_hidden_state

        if task == 'token_classification':
            # Pass the full token embeddings through the dedicated classifier head
            token_logits = self.token_classifier(full_token_embeddings)
            return token_logits

        elif task == 'sentence_similarity' or task == 'sequence_classification':
            # Extract the embedding of the [CLS] token (first token at index 0)
            cls_token_embedding = full_token_embeddings[:, 0, :]

            # Optional: Normalize the embedding (standard practice for similarity tasks)
            sentence_embedding = F.normalize(cls_token_embedding, p=2, dim=1)
            return sentence_embedding

        # Fallback: return the full embeddings for flexibility
        return full_token_embeddings


# --- Example Usage ---
if __name__ == '__main__':
    MODEL_NAME = "distilroberta-base"

    dora_model = DoRASentenceModel(
        model_name=MODEL_NAME,
        rank=8,
        alpha=16
    )

    dummy_input_ids = torch.randint(0, 50000, (2, 40))
    dummy_attention_mask = torch.ones((2, 40), dtype=torch.long)

    print("\n--- Token Classification Task ---")
    token_logits = dora_model(
        input_ids=dummy_input_ids,
        attention_mask=dummy_attention_mask,
        task='token_classification'
    )
    print(f"Token Logits Shape (B, L, C): {token_logits.shape}")
    # B=2 (batch), L=40 (length), C=10 (classes)

    print("\n--- Sentence Similarity Task ---")
    embeddings = dora_model(
        input_ids=dummy_input_ids,
        attention_mask=dummy_attention_mask,
        task='sentence_similarity'
    )
    print(f"Sentence Embedding Dimension (B, H): {embeddings.shape}")

    # Calculate cosine similarity
    similarity = F.cosine_similarity(embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0))
    print(f"Cosine Similarity (Sentence 1 vs. Sentence 2): {similarity.item():.4f}")

    # --- Training Note ---
    # For Multi-Task Training, you would call the model twice within your loop:
    # 1. Loss_Token = CrossEntropyLoss(dora_model(..., task='token_classification'), token_labels)
    # 2. Loss_Sim = ContrastiveLoss(dora_model(..., task='sentence_similarity'), similarity_labels)
    # 3. Total_Loss = Loss_Token + Loss_Sim
