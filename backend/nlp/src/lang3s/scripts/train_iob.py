import json
import random
from typing import Any, Dict, List, Tuple

from pydantic import Field

from lang3s.app import Application
from lang3s.models.training.iob import IObTrainer, TokenClassificationParams, TokenDataset
from lang3s.models.training.trainer import TrainerParams

cache = []


def run_trial(cfg, trial_id, parameters: Dict[str, Any], dataset, val_dataset):
    global cache
    params = TokenClassificationParams(**parameters)
    params = params.model_dump()
    params["learning_rate"] = cfg["lr"]
    params["num_attention_heads"] = cfg["heads"]
    params["dropout"] = cfg["dropout"]
    params["lora_rank"] = cfg["lora_rank"]
    params["dora_rank"] = cfg["dora_rank"]
    params["num_epochs"] = 5
    params["use_attention"] = True
    params["use_adapter"] = True
    params["window_radius"] = cfg["radius"]
    params["is_trial"] = True

    trainer = IObTrainer(
        name="test",
        annotation_type="test",
        **params,
        train_dataset=dataset,
        val_dataset=val_dataset
    )
    if len(cache) > 0:
        trainer.cache = cache

    trainer.train()

    if len(cache) == 0:
        cache = trainer.cache

    result = trainer.eval_one_epoch()
    f1 = result["span_f1"]
    print(f"[Trial {trial_id}] SpanF1={f1:.4f}  cfg={cfg}\n")
    return f1, params


def random_search(dataset: TokenDataset,
                  val_dataset: TokenDataset | None,
                  parameters: Dict[str, Any], n_trials=15):
    search_space = {
        "lora_rank": [4, 6, 8, 10],
        "dora_rank": [8, 12, 16],
        "radius": [2, 3],
        "heads": [2, 4],
        "dropout": [0.05, 0.1, 0.15],
        "lr": [1e-4, 2e-4, 3e-4],
    }

    keys = list(search_space.keys())
    best = None
    seen = set()

    for t in range(1, n_trials + 1):
        while True:
            cfg = {k: random.choice(search_space[k]) for k in keys}
            cfg_str = ", ".join(f"{k}={v}" for k, v in sorted(cfg.items(), key=lambda x: x[0]))
            if cfg_str not in seen:
                seen.add(cfg_str)
                break
        print(f"[Trial {t}] config={{{cfg_str}}}")
        result = run_trial(cfg, t, parameters, dataset, val_dataset)

        if best is None or result[0] > best[0]:
            best = result

    print("\nBEST CONFIG:", best)
    best_params = best[1]  # type: ignore
    best_params["is_trial"] = False
    best_params["num_epochs"] = parameters["num_epochs"]
    return best_params


def read_conll_file(path: str) -> List[Tuple[List[str], List[str]]]:
    sentences = []
    tokens, labels = [], []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                if len(tokens) > 0:
                    sentences.append((tokens, labels))
                    tokens, labels = [], []
            else:
                splits = line.split()
                token, label = splits[0], splits[-1]
                tokens.append(token)
                labels.append(label)

        if len(tokens) > 0:
            sentences.append((tokens, labels))

    return sentences


class TokenClassifier(Application, TrainerParams, TokenClassificationParams):
    """
    This application trains a token classifier.
    """
    auto_config: bool = Field(default=False, description="Automatically determine hyperparameters.")
    auto_config_trials: int = Field(default=5,
                                    description="Number of trials to run when searching for hyperparameters.")

    def run(self):
        train_dataset = TokenDataset(read_conll_file(self.train_data))
        val_dataset = None
        if self.val_data is not None:
            val_dataset = TokenDataset(read_conll_file(self.val_data))

        if val_dataset is not None:
            train_labels = set(train_dataset.label2idx.keys())
            val_labels = set(val_dataset.label2idx.keys())
            if len(val_labels.difference(train_labels)) > 0:
                print("Labels do not match")
                print("Train labels:", train_labels)
                print("Val labels:", val_labels)
                print("Missing labels:", val_labels.difference(train_labels))
                exit(1)

        print("Train data size:", len(train_dataset))
        if val_dataset is not None:
            print("Val data size:", len(val_dataset))
            
        parameters = dict(vars(self))
        if self.auto_config:
            best_parameters = random_search(train_dataset,
                                            val_dataset,
                                            parameters,
                                            n_trials=self.auto_config_trials)
            with open(f"{self.name}_best_parameters.json", "w") as f:
                json.dump(best_parameters, f, indent=2)
            parameters.update(best_parameters)

        trainer = IObTrainer(
            train_dataset=train_dataset,
            val_dataset=val_dataset,
            **parameters
        )
        trainer.train()


if __name__ == "__main__":
    TokenClassifier.from_cli().run()
