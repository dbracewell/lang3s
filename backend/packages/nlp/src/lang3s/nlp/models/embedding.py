import copy
import os
import sys

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel

# Note: This model works around an MPS bug which tries to optimize the ops in
# the AutoModel, but has instability.

TASK_MODELS = {
    "nli": {"compression": "nli_compressed.pt"},
    "search": {"layers": "search_layers.pt", "compression": "search_compressed.pt"},
}


class Lang3sMultiObjectiveEmbeddingModel(nn.Module):
    def __init__(self, base_model_name, unfreeze_last_n=2):
        super().__init__()
        config = AutoConfig.from_pretrained(base_model_name)
        total_layers = config.num_hidden_layers
        full_model = AutoModel.from_pretrained(
            base_model_name,
            torch_dtype=torch.float32,
        )

        split_layer = total_layers - unfreeze_last_n
        self.embeddings = full_model.embeddings
        self.shared_encoder = nn.ModuleList(full_model.encoder.layer[:split_layer])

        self.tasks = nn.ModuleDict(
            {
                "nli": nn.ModuleDict(
                    {
                        "layers": nn.ModuleList(full_model.encoder.layer[split_layer:]),
                        "compression": nn.Linear(config.hidden_size, 384),
                    }
                ),
                "search": nn.ModuleDict(
                    {
                        "layers": copy.deepcopy(
                            copy.deepcopy(
                                nn.ModuleList(full_model.encoder.layer[split_layer:])
                            )
                        ),
                        "compression": nn.Linear(config.hidden_size, 384),
                    }
                ),
            }
        )
        for task, layer2model in TASK_MODELS.items():
            for key, value in layer2model.items():
                model_file = os.path.join(base_model_name, value)
                if os.path.exists(model_file):
                    self.tasks[task][key].load_state_dict(
                        torch.load(model_file, map_location="cpu")
                    )
                else:
                    print(
                        f"Warning could not find {key} layer for {task}, "
                        "using random weights",
                        file=sys.stderr,
                        flush=True,
                    )

    def forward_trunk(self, input_ids, attention_mask):
        """Runs the shared bottom layers"""
        hidden_states = []

        x = self.embeddings(input_ids)

        extended_mask = attention_mask[:, None, None, :]
        dtype = x.dtype
        extended_mask = extended_mask.to(dtype=dtype)
        min_val = torch.finfo(dtype).min
        extended_mask = (1.0 - extended_mask) * min_val

        for layer in self.shared_encoder:
            x = layer(x, extended_mask)[0]
            hidden_states.append(x)
        return hidden_states, extended_mask

    def forward(self, input_ids, attention_mask, task="nli"):
        lower_states, mask = self.forward_trunk(input_ids, attention_mask)

        layers = self.tasks[task]["layers"]
        compressor = self.tasks[task]["compression"]

        hidden_state = lower_states[-1].contiguous()
        hidden_state = layers[0](hidden_state, mask)[0]
        for i in range(1, len(layers)):
            hidden_state = layers[i](hidden_state, mask)[0]

        return {
            "hidden_states": lower_states,
            "semantic_head": hidden_state,
            "compressor": compressor,
        }
