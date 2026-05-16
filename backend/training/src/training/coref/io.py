import torch


def save_preprocessed_data(documents, filepath):
    # 'documents' is your list of lists containing the mention dicts
    # PyTorch easily serializes nested standard Python objects + Tensors
    torch.save(documents, filepath)
    print(f"Saved {len(documents)} documents to {filepath}")


def load_preprocessed_data(filepath, device):
    # Weights_only=False is required here because we are loading custom
    # nested dictionaries, not just a model state_dict
    documents = torch.load(filepath, map_location=device, weights_only=False)
    print(f"Loaded {len(documents)} documents.")
    return documents
