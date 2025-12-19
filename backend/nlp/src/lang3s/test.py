from lang3s.app import Application
from lang3s.maths import binarize
from lang3s.models import Embedder


class Test(Application):

    def run(self):
        embedder = Embedder()
        v1 = embedder(["George Bush"]).sentence_embeddings[0]
        forked_model = embedder.model

        embedder.old()
        v2 = embedder(["George Bush"]).sentence_embeddings[0]
        ref_model = embedder.model

        print((v1 - v2).sum())

        import torch
        import numpy as np

        device = "cpu"
        inputs = embedder.tokenizer(
            ["George Bush"],
            return_tensors="pt",
            # padding="max_length",  # <--- MUST be set to max_length
            # max_length=20,  # <--- Force a length longer than the sentence
            # truncation=True
        ).to(device)

        # Setup
        input_ids = inputs["input_ids"]
        mask = inputs["attention_mask"]
        print(inputs["input_ids"])
        pad_id = embedder.tokenizer.pad_token_id
        print(f"Number of PAD tokens in input: {(input_ids == pad_id).sum().item()}")

        # 1. Run Reference Model
        ref_model.eval()
        ref_model.to(device)
        with torch.inference_mode():
            o = ref_model(input_ids, attention_mask=mask)
            ref_last_layer = o.last_hidden_state.cpu().float().numpy()
            # Capture the raw embedding output from the reference model
            # ref_embeds = ref_model.embeddings(input_ids)
            # ref_out = ref_model(input_ids, attention_mask=mask, output_hidden_states=True)
            # ref_layer0 = ref_out.hidden_states[1]  # [0] is embeddings, [1] is layer 0 output
            # ref_last_layer = ref_out.last_hidden_state

        # 2. Run Forked Model
        forked_model.eval()
        forked_model.to(device)
        with torch.inference_mode():
            # # Capture raw embeddings from forked model
            # fork_embeds = forked_model.embeddings(input_ids)
            # # Run trunk
            # trunk_out, trunk_mask = forked_model.forward_trunk(input_ids, mask)
            # fork_layer0 = trunk_out[0]  # Layer 0 is the first element in your stack
            # fork_last_layer = forked_model.nli_layers[0](trunk_out[-1], trunk_mask)[0]
            # for i in range(1, len(forked_model.nli_layers)):
            #     fork_last_layer = forked_model.nli_layers[i](fork_last_layer, trunk_mask)[0]

            fork_last_layer = forked_model(input_ids, attention_mask=mask)["semantic_head"].cpu().float().numpy()

        # 3. Compare
        # print(f"Embeddings Diff: {torch.abs(ref_embeds - fork_embeds).max().item()}")
        # print(f"Layer 0 Diff:    {torch.abs(ref_layer0 - fork_layer0).max().item()}")
        print(f"Last Layer  Diff:    {(ref_last_layer - fork_last_layer).sum().item()}")

        # # Check if the error is specifically on Padding Tokens vs Real Tokens
        # seq_len = input_ids.shape[1]
        # # Assuming padding_idx is 1
        # pad_mask = (input_ids == 1)
        # real_mask = ~pad_mask
        #
        # diff_tensor = torch.abs(ref_layer0 - fork_layer0)
        # print(f"Max Diff on REAL tokens: {diff_tensor[real_mask].max(dim=1)}")
        # print(f"Max Diff on PAD tokens:  {diff_tensor[pad_mask].max(dim=1)}")


if __name__ == "__main__":
    Test.from_cli().run_with_plugins()
