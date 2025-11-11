from typing import List, Tuple

from more_itertools import first

from lang3s.types.core_types import Document, Event, TextAnnotation
from lang3s.types.metadata import Metadata

IGNORE_VERBS = {
    "say",
    "note",
    "report",
    "be",
    "seem",
    "appear",
    "exist",
    "remain",
    "consist",
    "contain",
    "include",
    "involve",
    "comprise",
    "belong",
    "own",
    "have",
    "possess",
    "hold",
    "resemble",
    "equal",
    "match",
    "represent",
    "signify",
    "indicate",
    "mean",
    "imply",
    "express",
    "depend",
    "relate",
    "concern",
    "cost",
    "weigh",
    "measure",
    "owe",
    "lack",
    "require",
    "need",
    "want",
    "prefer",
    "desire",
    "love",
    "hate",
    "like",
    "dislike",
    "enjoy",
    "fear",
    "know",
    "believe",
    "think",
    "understand",
    "remember",
    "forget",
    "imagine",
    "realize",
    "suppose",
    "guess",
    "doubt",
    "agree",
    "disagree",
    "mean",
    "consider",
    "assume",
    "expect",
    "hope",
    "wish",
    "intend",
    "promise",
    "decide",
    "deny",
    "doubt",
    "recognize",
    "appreciate",
    "envy",
    "trust",
    "respect",
    "admire",
    "despise",
    "own",
    "possess",
    "belong",
    "consist",
    "contain",
    "include",
    "involve",
    "concern",
    "represent",
    "resemble",
    "signify",
    "indicate",
    "depend",
    "remain",
    "stay",
    "seem",
    "appear",
}


PERSON_PRONOUNS = [
    # personal
    "i",
    "me",
    "we",
    "us",
    "you",
    "he",
    "him",
    "she",
    "her",
    "they",
    "them",
    # possessive
    "my",
    "mine",
    "our",
    "ours",
    "your",
    "yours",
    "his",
    "her",
    "hers",
    "their",
    "theirs",
    # reflexive / intensive
    "myself",
    "yourself",
    "himself",
    "herself",
    "itself",
    "ourselves",
    "yourselves",
    "themselves",
    "themself",
    # indefinite (human-related)
    "anyone",
    "anybody",
    "everyone",
    "everybody",
    "someone",
    "somebody",
    "noone",
    "nobody",
    "each",
    "either",
    "neither",
    # relative / interrogative
    "who",
    "whom",
    "whose",
]

VERB_EVENT_MAP = {
    # Conflict
    "attack": "Conflict",
    "fight": "Conflict",
    "strike": "Conflict",
    "bomb": "Conflict",
    "protest": "Conflict",
    "defend": "Conflict",
    "invade": "Conflict",
    "shoot": "Conflict",
    "kill": "Conflict",
    # Movement
    "go": "Movement",
    "come": "Movement",
    "leave": "Movement",
    "move": "Movement",
    "arrive": "Movement",
    "travel": "Movement",
    "return": "Movement",
    "flee": "Movement",
    "enter": "Movement",
    "depart": "Movement",
    # Contact / Communication
    "meet": "Contact",
    "talk": "Contact",
    "call": "Contact",
    "speak": "Contact",
    "say": "Contact",
    "tell": "Contact",
    "discuss": "Contact",
    "report": "Contact",
    "announce": "Contact",
    # Creation / Construction
    "build": "Creation",
    "create": "Creation",
    "develop": "Creation",
    "design": "Creation",
    "write": "Creation",
    "invent": "Creation",
    "compose": "Creation",
    "produce": "Creation",
    # Destruction
    "destroy": "Destruction",
    "demolish": "Destruction",
    "burn": "Destruction",
    "damage": "Destruction",
    "remove": "Destruction",
    # Possession / Transfer
    "give": "Transfer",
    "take": "Transfer",
    "receive": "Transfer",
    "acquire": "Transfer",
    "borrow": "Transfer",
    "lend": "Transfer",
    "steal": "Transfer",
    # Justice / Legal
    "arrest": "Justice",
    "charge": "Justice",
    "sentence": "Justice",
    "sue": "Justice",
    "convict": "Justice",
    "judge": "Justice",
    "punish": "Justice",
    # Life / Death
    "die": "Life",
    "marry": "Life",
    "divorce": "Life",
    "born": "Life",
    "give_birth": "Life",
    # Social / Organization
    "join": "Organization",
    "resign": "Organization",
    "vote": "Organization",
    "elect": "Organization",
    "found": "Organization",
    "merge": "Organization",
    "split": "Organization",
    # Transaction / Financial
    "pay": "Transaction",
    "spend": "Transaction",
    "invest": "Transaction",
    "donate": "Transaction",
    "earn": "Transaction",
    "buy": "Transaction",
    "sell": "Transaction",
    # Change / Transformation
    "grow": "Change",
    "increase": "Change",
    "decrease": "Change",
    "improve": "Change",
    "expand": "Change",
    "transform": "Change",
    "change": "Change",
    # Emotion / Psychological
    "love": "Emotion",
    "hate": "Emotion",
    "enjoy": "Emotion",
    "fear": "Emotion",
    "regret": "Emotion",
    "admire": "Emotion",
    "prefer": "Emotion",
    # Weather / Environment
    "rain": "Weather",
    "snow": "Weather",
    "flood": "Weather",
    "storm": "Weather",
    "freeze": "Weather",
    "hail": "Weather",
}


def get_conjucts(token: TextAnnotation):
    tokens = [token]
    for child in token.children:
        if child.dep == "conj" and child.text != token.text:
            tokens.append(child)
    return tokens


def is_event_trigger(token: TextAnnotation):
    return (
        token.value == "VERB"
        and token.metadata[Metadata.LEMMA.value].lower() not in IGNORE_VERBS
    )


def process_a0_a1(array: List[TextAnnotation]):
    final_list = []
    for item in array:
        if item.type == "span":
            entity = first(item.entities, None)
            if entity is not None:
                final_list.append(entity)
            else:
                if item.text.lower() in PERSON_PRONOUNS:
                    item.type = "entity"
                    item.value = "PERSON"
                else:
                    item.type = "entity"
                    item.value = "MISC"
                item.owner.attach_annotation(item)
                final_list.append(item)
        else:
            final_list.append(item)

    return final_list


def expand_argument(annotation: TextAnnotation) -> TextAnnotation:
    if annotation.type == "token" and annotation.value == "VERB":
        start = annotation.start
        end = annotation.end
        for child in annotation.children:
            if child.value in ("AUX", "ADP") and child.dep in ("advmod"):
                start = min(start, child.start)
                end = max(end, child.end)
        return annotation.owner.create_span(start=start, end=end, value="VERB")

    chunks = [chunk for chunk in annotation.noun_chunks]
    if len(chunks) > 0:
        chunk = max(chunks, key=lambda c: c.end - c.start)
        start = annotation.start
        end = annotation.end
        for t in chunk.tokens:
            start = min(start, t.start)
            end = max(end, t.end)
        span = annotation.owner.create_span(start=start, end=end, value="VERB")
        entity = first(span.entities, None)
        if entity is not None:
            return entity
        return span

    # fallback: subtree
    start = annotation.start
    end = annotation.end
    for t in annotation.subtree:
        start = min(start, t.start)
        end = max(end, t.end)
    span = annotation.owner.create_span(start=start, end=end, value="VERB")
    entity = first(span.entities, None)
    if entity is not None:
        return entity
    return span


def extract_events(doc: Document) -> List[Event]:
    events: List[Event] = []
    if doc.text is None:
        return events

    sentences: List[TextAnnotation] = list(doc.text.sentences)
    for sent in sentences:
        triggers = [
            expand_argument(token)
            for token in sent.tokens
            if is_event_trigger(token)
        ]
        for trigger in triggers:
            event = Event(
                trigger, value=VERB_EVENT_MAP.get(trigger.lemma, trigger.lemma)
            )

            trigger_children: List[TextAnnotation] = []
            trigger_parents: List[Tuple[str, TextAnnotation | None]] = []
            for token in trigger.tokens:
                trigger_children.extend(token.children)
                trigger_parents.append((token.dep, token.parent))

            subs = [
                child
                for child in trigger_children
                if child.dep in ("nsubj", "nsubjpass")
            ]
            if len(subs) == 0:
                for dep, parent in trigger_parents:
                    if parent is None:
                        continue
                    if dep == "conj" and parent.value == "VERB":
                        subs.extend(
                            [
                                child
                                for child in parent.children
                                if child.dep in ("nsubj", "nsubjpass")
                            ]
                        )

            for s in subs:
                for tok in get_conjucts(s):
                    event.A0.append(expand_argument(tok))

            # Objects
            objs = [
                child
                for child in trigger_children
                if child.dep in ("dobj", "obj", "pobj")
            ]
            for o in objs:
                for tok in get_conjucts(o):
                    event.A1.append(expand_argument(tok))

            sent_times: List[TextAnnotation] = []
            sent_locs: List[TextAnnotation] = []
            for span in event.A1:
                for ent in span.entities:
                    if ent.value in ("GPE", "LOC", "FAC"):
                        sent_locs.append(ent)

            for child in trigger_children:
                if child.dep == "prep":
                    grandchildren = list(child.children)
                    for span in grandchildren:
                        span = expand_argument(span)

                        for ent in span.entities:
                            if ent.value in ("GPE", "LOC", "FAC"):
                                sent_locs.append(ent)
                            elif ent.value in ("DATE", "TIME"):
                                sent_times.append(ent)

            event.LOC = first(sent_locs, None)
            if event.LOC is not None:
                entity = first(event.LOC.entities, None)
                if entity is not None:
                    event.LOC = entity
                else:
                    event.LOC.type = "entity"
                    event.LOC.value = "LOC"
                    doc.text.attach_annotation(event.LOC)

            event.TIME = first(sent_times, None)
            if event.TIME is not None:
                entity = first(event.TIME.entities, None)
                if entity is not None:
                    event.TIME = entity
                else:
                    event.TIME.type = "entity"
                    event.TIME.value = "TIME"
                    doc.text.attach_annotation(event.TIME)

            event.A0 = process_a0_a1(event.A0)
            event.A1 = process_a0_a1(event.A1)

            events.append(event)
    return events
