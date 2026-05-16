import spacy
from spacy.tokens import DocBin
from spacy.training import biluo_tags_to_spans, iob_to_biluo

nlp = spacy.blank("en")


def parse_streusle_with_senses(filepath):
    sentences = []
    tokens = []
    iob_tags = []

    active_sense = "O"
    mwe_len = 0
    current_mwe_index = 0
    in_mwe = False

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                if tokens:
                    # Same cleanup as before to fix gappy MWEs
                    for i in range(len(iob_tags)):
                        if iob_tags[i].startswith("B-"):
                            if i == len(iob_tags) - 1 or not iob_tags[i + 1].startswith(
                                "I-"
                            ):
                                # If it's a single word, it's fine! Just ensure it's not a broken MWE.
                                pass
                    sentences.append((tokens, iob_tags))
                    tokens = []
                    iob_tags = []
                    active_mwe_id = None
                    active_sense = "O"
                continue

            if line.startswith("#"):
                continue

            parts = line.split("\t")

            word = parts[1]
            tags = parts[-1].split("|")
            current_target_sense = "O"
            for tag in tags:
                if tag.startswith("Supersense="):
                    current_target_sense = tag[len("Supersense=") :]
                if tag.startswith("MWELen="):
                    in_mwe = True
                    mwe_len = int(tag[len("MWELen=") :])
                    current_mwe_index = 1
            tokens.append(word)

            if in_mwe:
                if current_mwe_index == 1:
                    active_sense = current_target_sense
                    current_tag = f"B-{active_sense}" if active_sense != "O" else "O"
                elif active_sense != "O":
                    current_tag = f"I-{active_sense}"

                iob_tags.append(current_tag)

            else:
                current_tag = (
                    f"B-{current_target_sense}" if current_target_sense != "O" else "O"
                )
                active_sense = "O"
                iob_tags.append(current_tag)

            in_mwe = current_mwe_index < mwe_len
            if not in_mwe:
                mwe_len = 0
                current_mwe_index = 0
    return sentences


def convert_to_spacy(data, output_path):
    db = DocBin()

    for tokens, iob_tags in data:
        # Create a spaCy Doc from the raw tokens
        doc = spacy.tokens.Doc(nlp.vocab, words=tokens)

        # spaCy requires BILUO tags for accurate span creation
        try:
            biluo_tags = iob_to_biluo(iob_tags)
            spans = biluo_tags_to_spans(doc, biluo_tags)
            doc.ents = spans
            db.add(doc)
        except Exception as e:
            print(f"Skipping sentence due to tag alignment issue: {tokens}")
            print(f"Error: {e}")

    db.to_disk(output_path)
    print(f"Saved {len(db)} documents to {output_path}")


streusle_train_data = parse_streusle_with_senses(
    "/Users/ik/Downloads/data/streusle.ud_train.conllu"
)
streusle_dev_data = parse_streusle_with_senses(
    "/Users/ik/Downloads/data/streusle.ud_dev.conllu"
)
with open("/Users/ik/prj/data/streusle.conll", "w") as writer:
    for tokens, tags in streusle_train_data:
        for token, tag in zip(tokens, tags):
            writer.write(f"{token}\t{tag}\n")
        writer.write("\n")
# convert_to_spacy(streusle_train_data, "train.spacy")
# convert_to_spacy(streusle_dev_data, "dev.spacy")
