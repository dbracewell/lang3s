import numpy as np

from lang3s.data.models.claim import Certainty, ClaimType, Modality, Sentiment
from lang3s.data.schemas.claim import Claim
from lang3s.llm import LoRaClient, Message


class ClaimExtractor:
    def __init__(self):
        self._model = LoRaClient()

    def extract(self, document_id: str, sentences: list[str]) -> list[Claim]:
        if not sentences:
            return []
        response = self._model.sync_chat_last_event(
            messages=[Message.user(f"Extract claims from: {' '.join(sentences)}")],
            adapter_name="claim",
            temperature=0.0,
            max_completion_tokens=4096,
            stop=["<|im_end|>", "<|endoftext|>"],
        )
        all_claims: list[Claim] = []
        if not response.content:
            return all_claims

        for raw_claim in response.content.split("\n"):
            parsed_claim = _parse_claim_string(raw_claim)
            if parsed_claim:
                subject = parsed_claim["subject"]
                predicate = parsed_claim["predicate"]
                obj = parsed_claim["object"]
                stance = parsed_claim["stance"]
                if parsed_claim["modality"] in (
                    "factual",
                    "normative",
                    "hypothetical",
                    "conditional",
                    "predictive",
                ):
                    mod = Modality(parsed_claim["modality"])
                else:
                    mod = "factual"
                neg = parsed_claim["negation"]

                if parsed_claim["certainty"] in (
                    "certain",
                    "probable",
                    "possible",
                    "speculative",
                ):
                    certain = Certainty(parsed_claim["certainty"])
                else:
                    certain = Certainty.unknown

                time_param = parsed_claim["time"]
                loc = parsed_claim["location"]
                source = parsed_claim["source"]
                keywords = [
                    item.strip("' ")
                    for item in parsed_claim["keywords"].strip("[] ").split(",")
                ]

                if subject and predicate and obj:
                    all_claims.append(
                        Claim(
                            document_id=document_id,
                            subject=subject,
                            predicate=predicate,
                            type_=ClaimType.Fact,
                            object=obj,
                            stance=stance,
                            claim=f"{subject} {predicate} {obj}",
                            keywords=keywords,
                            time=time_param,
                            source=source,
                            evidence="",
                            location=loc,
                            embedding=np.zeros(1),
                            modality=mod,  # type: ignore
                            negation=neg.lower() == "true",
                            certainty=certain,  # type: ignore
                            condition="",
                            sentiment=Sentiment.neutral,
                        )
                    )

        return all_claims


def _parse_claim_string(text: str) -> dict | None:
    markers = {
        "SUBJ:": "subject",
        "PRED:": "predicate",
        "OBJ:": "object",
        "STANCE:": "stance",
        "MOD:": "modality",
        "NEG:": "negation",
        "CERTAIN:": "certainty",
        "TIME:": "time",
        "LOC:": "location",
        "SOURCE:": "source",
        "KW:": "keywords",
    }

    found_markers = []
    for marker, key in markers.items():
        idx = text.find(marker)
        if idx != -1:
            found_markers.append((idx, marker, key))

    if not found_markers:
        return None

    found_markers.sort(key=lambda x: x[0])

    parsed = {key: "" for key in markers.values()}

    for i in range(len(found_markers)):
        current_idx = found_markers[i][0]
        marker_length = len(found_markers[i][1])
        key = found_markers[i][2]
        start_idx = current_idx + marker_length

        if i + 1 < len(found_markers):
            end_idx = found_markers[i + 1][0]
        else:
            end_idx = len(text)

        parsed[key] = text[start_idx:end_idx].strip()

    if not (parsed["subject"] and parsed["predicate"] and parsed["object"]):
        return None

    return parsed
