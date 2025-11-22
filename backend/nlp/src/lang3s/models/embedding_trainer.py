import math
import os
import random

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
# Hugging Face imports for data pipeline
from datasets import load_dataset
from torch.utils.data import DataLoader, ConcatDataset
from transformers import AutoModel, AutoConfig, AutoTokenizer, get_linear_schedule_with_warmup


# --- 1. Model Architecture (DoRA and Task Heads) ---
def get_target_device():
    """Dynamically determines the best device (CUDA > MPS > CPU)."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    else:
        return torch.device("cpu")


DEVICE = get_target_device()
print(f"Target Device for Training: {DEVICE}")


class DoRALinear(nn.Module):
    """ A LoRA-based layer with Weight Decomposition (DoRA) applied. """

    def __init__(self, original_layer: nn.Linear, rank: int = 8, alpha: int = 16, device="cpu"):
        super().__init__()

        # Original weights are loaded first (on CPU/default device)
        self.original_weight = original_layer.weight.data
        self.original_weight.requires_grad = False
        self.bias = original_layer.bias

        self.in_features = original_layer.in_features
        self.out_features = original_layer.out_features

        self.scaling = alpha / rank

        # --- MPS FIX: Explicitly initialize new tensors on the DEVICE ---

        # Low-rank matrices
        self.lora_A = nn.Parameter(torch.empty(rank, self.in_features, device=device))
        self.lora_B = nn.Parameter(torch.empty(self.out_features, rank, device=device))

        # DoRA Magnitude Component (m)
        # We must initialize 'm' on the target device
        initial_m_value = torch.linalg.norm(self.original_weight, dim=1, keepdim=True).to(device)
        self.m = nn.Parameter(initial_m_value)

        # Move the original weight to the target device as well, since it's used in the forward pass
        self.original_weight = self.original_weight.to(DEVICE)
        if self.bias is not None:
            self.bias = self.bias.to(DEVICE)

        self.reset_parameters()

    def reset_parameters(self):
        # We perform initialization on the parameters which are already on the target device
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # All tensors (x, self.lora_A, self.lora_B, self.m, self.original_weight) are now guaranteed to be on the same device (DEVICE)
        delta_W = (self.lora_B @ self.lora_A) * self.scaling
        W_dir = self.original_weight + delta_W
        W_dir_norm = torch.linalg.norm(W_dir, dim=1, keepdim=True)

        W_DoRA = self.m * (W_dir / W_dir_norm)

        return F.linear(x, W_DoRA, self.bias)


class DoRASentenceModel(nn.Module):
    """
    Multi-task model structure. If 'task' is not a training task, it returns
    the normalized CLS embedding for sentence similarity/search.
    """

    def __init__(self, model_name: str, rank: int = 8, alpha: int = 16, num_binary_classes: int = 1,
                 num_token_classes: int = 7, device="cpu"):
        super().__init__()

        self.model_name = model_name
        self.rank = rank
        self.alpha = alpha
        self.device = device

        # We need to initialize the base model to get the original weights
        self.base_model = AutoModel.from_pretrained(model_name)
        self.base_model.to(device)

        for param in self.base_model.parameters():
            param.requires_grad = False

        # Inject DoRA layers into the base model
        self._inject_dora_layers()

        config = AutoConfig.from_pretrained(model_name)
        self.hidden_size = config.hidden_size

        # Task Heads (only needed during training)
        self.regression_head = nn.Linear(self.hidden_size, 1)
        self.binary_classifier = nn.Linear(self.hidden_size, num_binary_classes)
        self.token_classifier = nn.Linear(self.hidden_size, num_token_classes)

    def _inject_dora_layers(self):
        target_names = ["query", "value", "key", "dense"]

        for name, module in self.base_model.named_modules():
            if any(target in name for target in target_names) and isinstance(module, nn.Linear):
                parent_name, attr_name = name.rsplit('.', 1)
                parent_module = self.base_model.get_submodule(parent_name)

                new_dora_layer = DoRALinear(
                    original_layer=module,
                    rank=self.rank,
                    alpha=self.alpha,
                    device=self.device,
                )
                setattr(parent_module, attr_name, new_dora_layer)

    def to(self, device):
        """
        Custom 'to' method to ensure all tensors, including non-parameter
        original_weight tensors inside DoRALinear, are moved to the target device.
        """
        # 1. Call the standard nn.Module.to() to move all Parameters (A, B, m, and base weights/buffers)
        super().to(device)

        # 2. Manually iterate and move the non-registered tensors (original_weight)
        for module in self.modules():
            if isinstance(module, DoRALinear):
                # Move the stored original weight tensor
                module.original_weight = module.original_weight.to(device)
                if module.bias is not None:
                    module.bias = module.bias.to(device)

        print(f"All model components successfully moved to {device}")
        return self

    def forward(self, input_ids, attention_mask=None, token_type_ids=None, task='embedding'):
        outputs = self.base_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=True
        )

        full_token_embeddings = outputs.last_hidden_state
        cls_token_embedding = full_token_embeddings[:, 0, :]

        # NOTE: Only return embeddings for similarity/contrastive loss
        if task == 'embedding':
            return F.normalize(cls_token_embedding, p=2, dim=1)

        # Task Head branches
        elif task == 'token_classification':
            return self.token_classifier(full_token_embeddings)

        elif task == 'binary_classification':
            return self.binary_classifier(cls_token_embedding)

        elif task == 'regression':
            # This is for the supervised MSE loss (score prediction)
            return self.regression_head(cls_token_embedding)

        else:
            # Fallback for inference/deployment structure (returns normalized CLS)
            return F.normalize(cls_token_embedding, p=2, dim=1)


# --- Device Management and Debugging Function ---
def ensure_all_on_device(model, target_device):
    """
    Checks all parameters and buffers in the model and moves them to the target device.
    This is essential for custom modules like DoRA where .to(device) might miss
    non-parameter tensors or cause issues if the parameters were registered incorrectly.
    """
    print(f"--- Ensuring all tensors are on device: {target_device} ---")

    # Flag to track if any tensors were moved
    moved_count = 0

    # 1. Move the entire model using .to() first (standard PyTorch practice)
    model.to(target_device)

    # 2. Iterate and verify (especially useful for debugging custom modules)
    for name, param in model.named_parameters():
        if param.device.type != target_device.type:
            param.data = param.data.to(target_device)
            moved_count += 1
            print(f"MOVED (Param): {name} was on {param.device}, now on {param.data.device}")
        # else:
        # print(f"OK (Param): {name} is on {param.device}")

    for name, buffer in model.named_buffers():
        if buffer.device.type != target_device.type:
            # Buffers are non-learnable state, move them explicitly if .to() missed
            buffer.data = buffer.data.to(target_device)
            moved_count += 1
            print(f"MOVED (Buffer): {name} was on {buffer.device}, now on {buffer.data.device}")
        # else:
        # print(f"OK (Buffer): {name} is on {buffer.device}")

    if moved_count == 0:
        print("SUCCESS: All parameters and buffers were already correctly placed.")
    else:
        print(f"FIXED: Successfully moved {moved_count} tensors to {target_device}.")

    print("-------------------------------------------------")


# --- 2. Data Loading and Preprocessing Functions ---
def load_hf_dataset():
    """ Loads multilingual datasets for the three tasks. """
    all_datasets = []

    # Using 'train[:100]' for quick demonstration; in production, use the full 'train' split.

    # Regression (STS-B Multi)
    langs = ["fr", "en", "de", "es", "zh"]
    for lang in langs:
        d = load_dataset("stsb_multi_mt", lang, split='train')
        all_datasets.append((d, f'regression_stsb_{lang}'))

    # Binary Classification (XNLI adapted)
    langs = ["en", "es", "zh"]
    for lang in langs:
        d = load_dataset("xnli", lang, split='train')
        all_datasets.append((d, f'classification_xnli_{lang}'))

    # Token Classification (WikiAnn)
    langs = ["en", "es", "zh"]
    for lang in langs:
        d = load_dataset("wikiann", lang, split='train')
        all_datasets.append((d, f'token_classification_wikiann_{lang}'))

    return all_datasets


def preprocess_function(examples, task_name, tokenizer, max_length=64):
    """ Task-specific tokenization and label alignment.

    Uses task_name.startswith() for robust branching.
    """

    # Regression Tasks (Semantic Similarity)
    if task_name.startswith('regression'):
        result = tokenizer(
            examples['sentence1'], examples['sentence2'],
            padding='max_length',
            truncation=True,
            max_length=max_length
        )

        score_key = 'similarity_score'
        # Handle the case where the label column might be renamed in some datasets
        if score_key not in examples: score_key = 'label'

        # Store both sentences' inputs separately for the contrastive loss function
        result['input_ids_s1'] = \
            tokenizer(examples['sentence1'], padding='max_length', truncation=True, max_length=max_length)['input_ids']
        result['input_ids_s2'] = \
            tokenizer(examples['sentence2'], padding='max_length', truncation=True, max_length=max_length)['input_ids']
        result['attention_mask_s1'] = \
            tokenizer(examples['sentence1'], padding='max_length', truncation=True, max_length=max_length)[
                'attention_mask']
        result['attention_mask_s2'] = \
            tokenizer(examples['sentence2'], padding='max_length', truncation=True, max_length=max_length)[
                'attention_mask']

        result['label'] = [float(score) / 5.0 for score in examples[score_key]]
        return result

    # Binary Classification Tasks (NLI adaptation)
    elif task_name.startswith('classification'):

        result = tokenizer(
            examples['premise'], examples['hypothesis'],
            padding='max_length',
            truncation=True,
            max_length=max_length
        )

        # Binary Mapping: Entailment (0) -> 1.0, Others (1, 2) -> 0.0
        binary_labels = [1.0 if label == 0 else 0.0 for label in examples['label']]

        result['label'] = binary_labels
        return result

    # Token Classification Tasks (NER)
    elif task_name.startswith('token_classification'):

        def tokenize_and_align_labels(tokens, ner_tags):
            tokenized_inputs = tokenizer(
                tokens,
                is_split_into_words=True,
                truncation=True,
                max_length=max_length,
                padding='max_length'
            )

            labels = []
            word_ids = tokenized_inputs.word_ids()
            previous_word_idx = None

            for word_idx in word_ids:
                if word_idx is None:
                    labels.append(-100)
                elif word_idx != previous_word_idx:
                    labels.append(ner_tags[word_idx])
                else:
                    labels.append(-100)
                previous_word_idx = word_idx

            return {
                'input_ids': tokenized_inputs['input_ids'],
                'attention_mask': tokenized_inputs['attention_mask'],
                'label': labels,
            }

        processed_batch = [
            tokenize_and_align_labels(tokens, ner_tags)
            for tokens, ner_tags in zip(examples['tokens'], examples['ner_tags'])
        ]

        result = {
            'input_ids': [item['input_ids'] for item in processed_batch],
            'attention_mask': [item['attention_mask'] for item in processed_batch],
            'label': [item['label'] for item in processed_batch],
        }

        return result

    else:
        # Fallback for safety, though should not be reached
        raise ValueError(f"Unknown task name encountered: {task_name}")


def multi_task_collator(batch):
    """ Groups batch items by task type for efficient processing and converts lists to tensors. """
    tasks = {'regression': [], 'binary_classification': [], 'token_classification': []}
    for item in batch:
        task_type = item.pop('task_type')
        tasks[task_type].append(item)

    collated = {}

    for task_type, items in tasks.items():
        if items:
            if task_type == 'regression':
                # Special handling for regression to separate sentence pairs for contrastive loss
                collated[f'{task_type}_input_ids_s1'] = torch.stack(
                    [torch.tensor(item['input_ids_s1']) for item in items])
                collated[f'{task_type}_attention_mask_s1'] = torch.stack(
                    [torch.tensor(item['attention_mask_s1']) for item in items])
                collated[f'{task_type}_input_ids_s2'] = torch.stack(
                    [torch.tensor(item['input_ids_s2']) for item in items])
                collated[f'{task_type}_attention_mask_s2'] = torch.stack(
                    [torch.tensor(item['attention_mask_s2']) for item in items])

                # The raw pair inputs are still needed for the MSE regression head
                collated[f'{task_type}_input_ids'] = torch.stack([torch.tensor(item['input_ids']) for item in items])
                collated[f'{task_type}_attention_mask'] = torch.stack(
                    [torch.tensor(item['attention_mask']) for item in items])

            else:
                # Standard batching for other tasks
                collated[f'{task_type}_input_ids'] = torch.stack([torch.tensor(item['input_ids']) for item in items])
                collated[f'{task_type}_attention_mask'] = torch.stack(
                    [torch.tensor(item['attention_mask']) for item in items])

            collated[f'{task_type}_labels'] = torch.tensor([item['label'] for item in items])

    return collated


# --- 3. Training and Saving Functions & Loss Implementations ---

def multiple_negative_ranking_loss(emb_a, emb_b, temperature=0.1):
    """
    Calculates the Multiple Negative Ranking Loss (MNRL).

    emb_a and emb_b are the embeddings of the positive pairs (S1, S2).
    In-batch negatives: S1_i vs S2_j (j!=i) and S2_i vs S1_j (j!=i).

    NOTE: Temperature raised to 0.1 for stability against embedding space collapse.
    """

    # 1. Calculate similarity matrix (logits)
    # Sim(A, B) where Sim[i, j] is the similarity between A[i] and B[j]
    # Matrix shape: (batch_size, batch_size)
    cos_sim = F.cosine_similarity(emb_a.unsqueeze(1), emb_b.unsqueeze(0), dim=2) / temperature

    # 2. Targets: The positive pair is the main diagonal.
    # Target for A -> B: index i matches A[i] with B[i], so the target is the identity (0 to batch_size-1)
    labels = torch.arange(cos_sim.size(0)).long().to(cos_sim.device)

    # 3. Compute Cross-Entropy Loss (A vs B)
    # Logits: cos_sim (B x B). Target: labels (B)
    loss_a = F.cross_entropy(cos_sim, labels)

    # 4. Compute Cross-Entropy Loss (B vs A)
    # The transposed matrix means Sim[i, j] is now B[i] vs A[j].
    # The diagonal is still the positive pair.
    loss_b = F.cross_entropy(cos_sim.t(), labels)

    # 5. Total loss is the mean of the two directions
    return (loss_a + loss_b) / 2


def train_multitask(model, dataloader, config):
    """ The main multi-task training loop, now including contrastive loss. """
    device = config['device']
    model.to(device)
    model.train()

    params_to_update = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params_to_update, lr=config['learning_rate'])

    reg_loss_fn = nn.MSELoss()
    cls_loss_fn = nn.BCEWithLogitsLoss()
    tok_loss_fn = nn.CrossEntropyLoss(ignore_index=-100)

    num_training_steps = len(dataloader) * config['num_epochs']
    num_warmup_steps = int(num_training_steps * config['warmup_ratio'])

    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=num_warmup_steps, num_training_steps=num_training_steps
    )

    print("NOTE: Training started. Showing step logs.")

    for epoch in range(config['num_epochs']):
        total_epoch_loss = 0.0

        for step, batch in enumerate(dataloader):

            loss_regression = torch.tensor(0.0, device=device)
            loss_classification = torch.tensor(0.0, device=device)
            loss_token = torch.tensor(0.0, device=device)
            loss_contrastive = torch.tensor(0.0, device=device)
            total_loss = torch.tensor(0.0, device=device)

            # 1. Regression Tasks: Semantic Similarity (MNRL + MSE)
            if 'regression_input_ids' in batch:
                # --- A. Contrastive Loss (MNRL) ---
                # Requires separating the sentence pairs and using task='embedding'
                reg_input_ids_s1 = batch['regression_input_ids_s1'].to(device)
                reg_attention_mask_s1 = batch['regression_attention_mask_s1'].to(device)
                reg_input_ids_s2 = batch['regression_input_ids_s2'].to(device)
                reg_attention_mask_s2 = batch['regression_attention_mask_s2'].to(device)

                emb_s1 = model(reg_input_ids_s1, reg_attention_mask_s1, task='embedding')
                emb_s2 = model(reg_input_ids_s2, reg_attention_mask_s2, task='embedding')

                # MNRL is called here with the new, less aggressive temperature (0.1)
                loss_contrastive = multiple_negative_ranking_loss(emb_s1, emb_s2, temperature=0.1)
                total_loss += loss_contrastive * config['contrastive_loss_weight']

                # --- B. Supervised Regression Loss (MSE) ---
                # Requires the concatenated pair and using task='regression'
                reg_input_ids = batch['regression_input_ids'].to(device)
                reg_attention_mask = batch['regression_attention_mask'].to(device)
                reg_labels = batch['regression_labels'].to(device).float()

                reg_logits = model(reg_input_ids, reg_attention_mask, task='regression')

                loss_regression = reg_loss_fn(reg_logits.squeeze(-1), reg_labels.squeeze(-1))
                total_loss += loss_regression * config['reg_loss_weight']

            # 2. Binary Classification Task (NLI)
            if 'binary_classification_input_ids' in batch:
                cls_input_ids = batch['binary_classification_input_ids'].to(device)
                cls_attention_mask = batch['binary_classification_attention_mask'].to(device)
                cls_labels = batch['binary_classification_labels'].to(device).float()

                cls_logits = model(cls_input_ids, cls_attention_mask, task='binary_classification')

                cls_labels = cls_labels.squeeze(-1) if cls_labels.dim() > 1 and cls_labels.size(-1) == 1 else cls_labels

                loss_classification = cls_loss_fn(cls_logits.squeeze(-1), cls_labels)
                total_loss += loss_classification * config['cls_loss_weight']

            # 3. Token Classification Task (NER)
            if 'token_classification_input_ids' in batch:
                tok_input_ids = batch['token_classification_input_ids'].to(device)
                tok_attention_mask = batch['token_classification_attention_mask'].to(device)
                tok_labels = batch['token_classification_labels'].to(device).long()

                tok_logits = model(tok_input_ids, tok_attention_mask, task='token_classification')

                tok_logits_flat = tok_logits.view(-1, config['num_token_classes'])
                tok_labels_flat = tok_labels.view(-1)

                loss_token = tok_loss_fn(tok_logits_flat, tok_labels_flat)
                total_loss += loss_token * config['token_loss_weight']

            # --- Optimization ---
            if total_loss.item() > 0:
                total_loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), config['max_grad_norm'])

                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

                total_epoch_loss += total_loss.item()

                if step % 5 == 0:
                    print(f"Epoch {epoch + 1} | Step {step} | Total Loss: {total_loss.item():.4f} "
                          f"| Cont: {loss_contrastive.item():.4f} | Reg: {loss_regression.item():.4f} "
                          f"| Cls: {loss_classification.item():.4f} | Tok: {loss_token.item():.4f}")

        print(f"\nEpoch {epoch + 1} finished. Avg Loss: {total_epoch_loss / len(dataloader):.4f}")


def _get_dora_model_code():
    """
    Returns the source code for DoRALinear and DoRASentenceModel
    for saving to the deployment directory.
    """
    return """
import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from transformers import AutoModel, AutoConfig

class DoRALinear(nn.Module):
    def __init__(self, original_layer: nn.Linear, rank: int = 8, alpha: int = 16):
        super().__init__()
        # Simplified loading assumes original weights are loaded externally or set up here
        self.original_weight = original_layer.weight.data
        self.original_weight.requires_grad = False
        self.bias = original_layer.bias

        self.in_features = original_layer.in_features
        self.out_features = original_layer.out_features

        # Parameters must be initialized if they are part of the state dict
        self.lora_A = nn.Parameter(torch.empty(rank, self.in_features))
        self.lora_B = nn.Parameter(torch.empty(self.out_features, rank))
        self.scaling = alpha / rank

        self.m = nn.Parameter(
            torch.linalg.norm(self.original_weight, dim=1, keepdim=True)
        )
        # Note: reset_parameters() is skipped here as weights are loaded from disk

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        delta_W = (self.lora_B @ self.lora_A) * self.scaling
        W_dir = self.original_weight + delta_W
        W_dir_norm = torch.linalg.norm(W_dir, dim=1, keepdim=True)

        W_DoRA = self.m * (W_dir / W_dir_norm)
        return F.linear(x, W_DoRA, self.bias)

class DoRASentenceModel(nn.Module):
    def __init__(self, config):
        super().__init__()

        # Read custom parameters from config
        self.rank = config.rank
        self.alpha = config.alpha
        self.base_model_name = config.base_model_name
        self.hidden_size = config.hidden_size

        # Load the base model (weights will be overridden by the state dict load)
        self.base_model = AutoModel.from_pretrained(self.base_model_name)

        # Reinject DoRA layers using parameters saved in the config
        self._inject_dora_layers(self.rank, self.alpha)

        # Identity heads are placeholders since we only care about the base model output for inference
        self.regression_head = nn.Identity() 
        self.binary_classifier = nn.Identity() 
        self.token_classifier = nn.Identity()

    def _inject_dora_layers(self, rank, alpha):
        target_names = ["query", "value", "key", "dense"] 
        # Recursively search and replace nn.Linear with DoRALinear
        def replace_linear(module, rank, alpha):
            for name, sub_module in module.named_children():
                if any(target in name for target in target_names) and isinstance(sub_module, nn.Linear):
                    # We must pass the original linear layer to DoRALinear
                    new_dora_layer = DoRALinear(
                        original_layer=sub_module,
                        rank=rank,
                        alpha=alpha
                    )
                    setattr(module, name, new_dora_layer)
                else:
                    replace_linear(sub_module, rank, alpha)

        replace_linear(self.base_model, rank, alpha)

    def forward(self, input_ids, attention_mask=None, token_type_ids=None):
        # Runs the forward pass and returns all relevant embeddings (the user-requested dict structure).
        outputs = self.base_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=True
        )

        token_embeddings = outputs.last_hidden_state
        cls_token_embedding = token_embeddings[:, 0, :]

        # Normalized CLS token embedding (standard practice for sentence similarity)
        sentence_embedding = F.normalize(cls_token_embedding, p=2, dim=1)

        return {
            'token_embeddings': token_embeddings,
            'sentence_embedding': sentence_embedding,
            'hidden_states': outputs, # returns the full BaseModelOutputWithPooling or similar
        }
"""


def save_model_for_deployment(model, tokenizer, config):
    """
    Saves the model in a format that supports automatic loading via
    AutoModel.from_pretrained(..., trust_remote_code=True).
    """
    deployment_dir = "dora_inference_model"
    os.makedirs(deployment_dir, exist_ok=True)

    # 1. Save Tokenizer
    tokenizer.save_pretrained(deployment_dir)

    # 2. Save custom Python code file
    modeling_filepath = os.path.join(deployment_dir, 'modeling_dora.py')
    with open(modeling_filepath, 'w') as f:
        f.write(_get_dora_model_code())
    print(f"Custom model code saved to: {modeling_filepath}")

    # 3. Save the modified base model's state_dict (all DoRA weights)
    # We only save the base_model weights, as that is the intended deployable artifact.
    base_model_state = model.base_model.state_dict()
    torch.save(base_model_state, os.path.join(deployment_dir, 'pytorch_model.bin'))

    # 4. Modify and save the configuration file
    base_config = AutoConfig.from_pretrained(config['model_name'])

    # Add custom parameters needed for DoRASentenceModel instantiation
    base_config.architectures = ["DoRASentenceModel"]
    base_config.trust_remote_code = True
    base_config.base_model_name = config['model_name']
    base_config.rank = config['rank']
    base_config.alpha = config['alpha']
    base_config.hidden_size = model.hidden_size

    # The 'auto_map' is crucial for AutoModel to find the class in the custom file
    base_config.auto_map = {
        "AutoModel": "modeling_dora.DoRASentenceModel"
    }

    # Save the updated config
    base_config.save_pretrained(deployment_dir)

    print(f"\nDeployment artifacts saved to: '{deployment_dir}'")
    print("Model is now ready to be loaded automatically.")
    print("\n--- NEW INFERENCE OUTPUT STRUCTURE (as requested) ---")
    print("The model's forward pass now returns a dictionary:")
    print("{ 'token_embeddings': Tensor, 'sentence_embedding': Tensor, 'hidden_states': ModelOutput }")
    print("--------------------------------------")


# --- 4. Inference Function (Updated to reflect AutoModel loading concept) ---

def inference_test(model, tokenizer, config):
    # This function is now illustrative of the manual loading path.
    MODEL_PATH = config['save_path']
    device = torch.device(DEVICE)
    ensure_all_on_device(model, device)

    try:
        print(f"Loading full model weights from: {MODEL_PATH}")
        # Note: This loads the *full* training model, not the deployment one.
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        model.to(device)
        model.eval()
        print("Model loaded and set to evaluation mode.")
    except FileNotFoundError:
        print(f"Error: Model file '{MODEL_PATH}' not found. Please run the training mode first.")
        return
    except Exception as e:
        print(f"Error loading model weights: {e}")
        return

    sentences = [
        "J'aime le chat noir qui dort sur le tapis.",  # French
        "Ich mag die Katze, die auf der Matte schläft.",  # German (Semantically Similar)
        "The financial report detailed a sharp increase in quarterly revenue.",  # English (Different Topic)
    ]

    encoded_input = tokenizer(
        sentences,
        padding='max_length',
        truncation=True,
        max_length=config['max_length'],
        return_tensors='pt'
    ).to(device)

    print("\nGenerating Embeddings...")
    with torch.no_grad():
        # NOTE: This uses the forward method of the *original* DoRASentenceModel (the training class),
        # which returns the normalized tensor when task='embedding'.
        embeddings = model(
            input_ids=encoded_input['input_ids'],
            attention_mask=encoded_input['attention_mask'],
            task='embedding'
        )

    print(f"Generated Embeddings Shape: {embeddings.shape}")

    sim_fr_de = F.cosine_similarity(embeddings[0].unsqueeze(0), embeddings[1].unsqueeze(0)).item()
    sim_fr_en = F.cosine_similarity(embeddings[0].unsqueeze(0), embeddings[2].unsqueeze(0)).item()

    print("\n--- Semantic Similarity Results (0.0 to 1.0) ---")
    print(f"French vs. German (High Similarity Expected): {sim_fr_de:.4f}")
    print(f"French vs. English (Low Similarity Expected): {sim_fr_en:.4f}")
    print("\nInference Test Complete. The model successfully produced normalized sentence embeddings.")


# --- 5. Configuration and Main Execution ---

if __name__ == '__main__':

    # === SWITCH MODE HERE: 'train' or 'inference' ===
    RUN_MODE = 'train'
    # ===============================================

    config = {
        'model_name': "xlm-roberta-base",
        'max_length': 512,
        'batch_size': 16,
        'num_epochs': 30,
        'learning_rate': 2e-4,
        'rank': 8,
        'alpha': 16,

        'reg_loss_weight': 0.5,
        'cls_loss_weight': 0.7,
        'token_loss_weight': 1.0,
        'contrastive_loss_weight': 1.0,  # REDUCED: Weight lowered to 1.0 for stability

        'warmup_ratio': 0.06,
        'max_grad_norm': 1.0,

        'num_binary_classes': 1,
        'num_token_classes': 7,

        'save_path': 'dora_multitask_model.pt',

        "device": DEVICE
    }

    SEED = 42
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    tokenizer = AutoTokenizer.from_pretrained(config['model_name'])

    dora_model = DoRASentenceModel(
        model_name=config['model_name'],
        rank=config['rank'],
        alpha=config['alpha'],
        num_binary_classes=config['num_binary_classes'],
        num_token_classes=config['num_token_classes'],
        device=config['device']
    )
    dora_model.to(config['device'])

    if RUN_MODE == 'train':
        print(f"--- Running in TRAINING Mode ---")

        task_prefix_map = {
            'regression': 'regression',
            'classification': 'binary_classification',
            'token': 'token_classification',
        }

        dataset_task_pairs = load_hf_dataset()
        all_processed_datasets = []

        for raw_dataset, task_name in dataset_task_pairs:
            print(f"  -> Preprocessing {task_name}...")

            processed_ds = raw_dataset.map(
                preprocess_function,
                fn_kwargs={'task_name': task_name,
                           'tokenizer': tokenizer,
                           'max_length': config['max_length']},
                batched=True,
                # remove_columns=raw_dataset.column_names
            )

            task_prefix = task_name.split('_')[0]
            task_identifier = task_prefix_map.get(task_prefix, task_prefix)

            processed_ds = processed_ds.add_column("task_type", [task_identifier] * len(processed_ds))
            all_processed_datasets.append(processed_ds)

        unified_dataset = ConcatDataset(all_processed_datasets)

        dataloader = DataLoader(
            unified_dataset,
            batch_size=config['batch_size'],
            collate_fn=multi_task_collator,
            shuffle=True
        )

        ensure_all_on_device(dora_model, config['device'])

        print(f"\nTotal Combined Samples: {len(unified_dataset):,}")
        train_multitask(dora_model, dataloader, config)

        torch.save(dora_model.state_dict(), config['save_path'])
        print(f"Full model state saved to: {config['save_path']}")

        # --- DEPLOYMENT STEP WITH trust_remote_code support ---
        save_model_for_deployment(dora_model, tokenizer, config)


    elif RUN_MODE == 'inference':
        print(f"--- Running in INFERENCE Mode ---")
        inference_test(dora_model, tokenizer, config)

    else:
        print(f"Error: RUN_MODE '{RUN_MODE}' is unknown. Please use 'train' or 'inference'.")
