import copy
import os
import sys

import torch
import torch.nn as nn
from transformers import AutoModel, AutoConfig


### Note: This model works around an MPS bug which tries to optimize the ops in the AutoModel, but has instability.


class ForkedBaseModel(nn.Module):
    def __init__(self,
                 base_model_name,
                 unfreeze_last_n=2):
        super().__init__()
        config = AutoConfig.from_pretrained(base_model_name)
        total_layers = config.num_hidden_layers
        full_model = AutoModel.from_pretrained(base_model_name, torch_dtype=torch.float32, )

        split_layer = total_layers - unfreeze_last_n
        self.embeddings = full_model.embeddings
        self.shared_encoder = nn.ModuleList(full_model.encoder.layer[:split_layer])

        self.nli_layers = nn.ModuleList(full_model.encoder.layer[split_layer:])
        self.nli_compression = nn.Linear(config.hidden_size, 384)
        self.search_layers = copy.deepcopy(self.nli_layers)
        self.search_compression = copy.deepcopy(self.nli_compression)

        if os.path.exists(os.path.join(base_model_name, "nli_compressed.pt")):
            self.nli_compression.load_state_dict(torch.load(os.path.join(base_model_name, "nli_compressed.pt")))
        else:
            print("Warning could not find compression layer for nli, using random weights", file=sys.stderr, flush=True)

        if os.path.exists(os.path.join(base_model_name, "search_layers.pt")):
            self.search_layers.load_state_dict(torch.load(os.path.join(base_model_name, "search_layers.pt")))
        else:
            print("Warning could not find search layers for search, using nli weights", file=sys.stderr, flush=True)

        if os.path.exists(os.path.join(base_model_name, "search_compressed.pt")):
            self.search_compression.load_state_dict(torch.load(os.path.join(base_model_name, "search_compressed.pt")))
        else:
            print("Warning could not find compression layer for search, using nli weights", file=sys.stderr, flush=True)

    def forward_trunk(self, input_ids, attention_mask):
        """Runs the shared bottom layers (0-9)"""
        hidden_states = []

        x = self.embeddings(input_ids)

        extended_mask = attention_mask[:, None, None, :]
        dtype = x.dtype
        extended_mask = extended_mask.to(dtype=dtype)
        # extended_mask = (1.0 - extended_mask) * -10000.0
        min_val = torch.finfo(dtype).min
        extended_mask = (1.0 - extended_mask) * min_val

        for layer in self.shared_encoder:
            x = layer(x, extended_mask)[0]
            hidden_states.append(x)
        return torch.stack(hidden_states, dim=0), extended_mask

    def forward(self, input_ids, attention_mask, task="nli"):
        lower_states, mask = self.forward_trunk(input_ids, attention_mask)

        if task == "nli":
            layers = self.nli_layers
            compressor = self.nli_compression
        elif task == "search":
            layers = self.search_layers
            compressor = self.search_compression
        else:
            raise ValueError(f"Unknown task: {task}")

        # 3. Run Specific Transformer Layers (10-11)
        hidden_state = lower_states[-1].contiguous()
        hidden_state = layers[0](hidden_state, mask)[0]
        for i in range(1, len(layers)):
            hidden_state = layers[i](hidden_state, mask)[0]

        return {
            "hidden_states": lower_states,
            "semantic_head": hidden_state,
            "compressor": compressor
        }
