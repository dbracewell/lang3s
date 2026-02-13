import gzip
import importlib.resources
import json
from typing import List, Tuple

from more_itertools import first

from lang3s.nlp.language import is_person_pronoun
from lang3s.nlp.shared_types import Document, Event, Metadata, TextAnnotation
from lang3s.utils.meta import SingletonMeta

IGNORE_VERBS = {
    "be",
}


class FrameNetMapper(metaclass=SingletonMeta):
    def __init__(self):
        self.VERB_EVENT_MAP = {}
        with (
            importlib.resources.files("lang3s.nlp")
            .joinpath("verb_mapping.gz")
            .open("rb") as f_in
        ):
            with gzip.open(f_in, "rt") as f_gz:
                self.VERB_EVENT_MAP = json.load(f_gz)

    def get_category(self, language: str, verb: str):
        if language not in self.VERB_EVENT_MAP:
            return None
        mapping = self.VERB_EVENT_MAP[language]
        if verb not in mapping:
            return None
        return mapping[verb].lower()


def get_conjucts(token: TextAnnotation):
    tokens = [token]
    for child in token.children:
        if child.dep == "conj" and child.text != token.text:
            tokens.append(child)
    return tokens


def is_event_trigger(token: TextAnnotation):
    return (
        token.value == "VERB"
        and token[Metadata.LEMMA.value].lower() not in IGNORE_VERBS
    )


def process_a0_a1(array: List[TextAnnotation]):
    final_list = []
    for item in array:
        if item.type == "span":
            entity = first(item.entities, None)
            if entity is not None:
                final_list.append(entity)
            else:
                if is_person_pronoun(item):
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
            if child.value in ("AUX", "ADP") and child.dep in ("advmod", "aux"):
                start = min(start, child.start)
                end = max(end, child.end)
        return annotation.owner.create_span(
            start=start,
            end=end,
            value="VERB",
            source="rb_event_extractor",
        )

    chunks = [chunk for chunk in annotation.noun_chunks]
    if len(chunks) > 0:
        chunk = max(chunks, key=lambda c: c.end - c.start)
        start = annotation.start
        end = annotation.end
        for t in chunk.tokens:
            start = min(start, t.start)
            end = max(end, t.end)
        span = annotation.owner.create_span(
            start=start,
            end=end,
            value="VERB",
            source="rb_event_extractor",
        )
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
    span = annotation.owner.create_span(
        start=start,
        end=end,
        value="VERB",
        source="rb_event_extractor",
    )
    entity = first(span.entities, None)
    if entity is not None:
        return entity
    return span


def extract_events(doc: Document) -> List[Event]:
    mapper = FrameNetMapper()
    events: List[Event] = []
    if doc.text is None:
        return events

    sentences: List[TextAnnotation] = list(doc.text.sentences)
    for sent in sentences:
        triggers = [
            expand_argument(token) for token in sent.tokens if is_event_trigger(token)
        ]
        for trigger in triggers:
            mapping = mapper.get_category(doc.language, trigger.lemma)
            if mapping is None:
                continue

            type, value = mapping.split(":")
            trigger.type = type
            trigger.value = value
            trigger.source = "rb_event_extractor"
            event = Event(trigger)
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
                if child.dep in ("dobj", "obj", "pobj", "ccomp")
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
            if event.A1 or event.A0:
                events.append(event)
    return events
