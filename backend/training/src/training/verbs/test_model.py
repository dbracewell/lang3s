import spacy

# Load your newly trained model
nlp_mwe = spacy.load("./models/model-best")

# Test sentences
texts = [
    "I need to figure out how to set up this software.",
    "He suddenly passed away last night.",
]

for text in texts:
    doc = nlp_mwe(text)
    print(f"\nSentence: {text}")
    print("Detected MWEs:")
    for ent in doc.ents:
        if ent.label_ == "MWE":
            print(f" - {ent.text}")
