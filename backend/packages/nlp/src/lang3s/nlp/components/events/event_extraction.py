import gzip
import importlib.resources
import json

from more_itertools import first

from lang3s.core.typing_extras import SingletonMeta
from lang3s.data.schemas import Document, Event, Metadata, TextAnnotation
from lang3s.nlp.language import is_person_pronoun

IGNORE_VERBS = {
    "be",
}


class FrameNetMapper(metaclass=SingletonMeta):
    def __init__(self):
        self.VERB_EVENT_MAP = {}
        with (
            importlib.resources.files("lang3s.nlp.components.events")
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
        if child.dep == "conj" and child.content != token.content:
            tokens.append(child)
    return tokens


def is_event_trigger(token: TextAnnotation):
    return (
        token.value == "VERB"
        and token[Metadata.LEMMA.value].lower() not in IGNORE_VERBS
    )


def process_a0_a1(array: list[TextAnnotation]):
    final_list = []
    for item in array:
        if item.type_ == "span":
            entity = first(item.entities, None)
            if entity is not None:
                final_list.append(entity)
            else:
                if is_person_pronoun(item):
                    item.type_ = "entity"
                    item.value = "Person"
                else:
                    item.type_ = "entity"
                    item.value = "MISC"
                item.owner.attach_annotation(item)
                final_list.append(item)
        else:
            final_list.append(item)

    return final_list


def expand_trigger(annotation: TextAnnotation):
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


def expand_argument(annotation: TextAnnotation) -> TextAnnotation:
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


def extract_events(doc: Document) -> list[Event]:
    mapper = FrameNetMapper()
    events: list[Event] = []
    if doc.text is None:
        return events

    sentences: list[TextAnnotation] = list(doc.text.sentences)
    for sent in sentences:
        triggers = [
            expand_trigger(token) for token in sent.tokens if is_event_trigger(token)
        ]
        for trigger in triggers:
            mapping = mapper.get_category(doc.language, trigger.lemma)
            if mapping is None:
                continue

            type, value = mapping.split(":")
            trigger.type_ = type
            trigger.value = value
            trigger.source = "rb_event_extractor"
            event = Event(trigger=trigger)
            trigger_children: list[TextAnnotation] = []
            trigger_parents: list[tuple[str, TextAnnotation | None]] = []
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
                    event.a0.append(expand_argument(tok))

            # Objects
            objs = [
                child
                for child in trigger_children
                if child.dep in ("dobj", "obj", "pobj", "ccomp")
            ]
            for o in objs:
                for tok in get_conjucts(o):
                    event.a1.append(expand_argument(tok))

            sent_times: list[TextAnnotation] = []
            sent_locs: list[TextAnnotation] = []
            for span in event.a1:
                for ent in span.entities:
                    if ent.value in (
                        "GPE",
                        "LOC",
                        "FAC",
                        "GEO_POLITICAL_ENTITY",
                        "LOCATION",
                        "FACILITY",
                    ):
                        sent_locs.append(ent)

            for child in trigger_children:
                if child.dep == "prep":
                    grandchildren = list(child.children)
                    for span in grandchildren:
                        span = expand_argument(span)

                        for ent in span.entities:
                            if ent.value.upper() in (
                                "GPE",
                                "LOC",
                                "FAC",
                                "GEO_POLITICAL_ENTITY",
                                "LOCATION",
                                "FACILITY",
                            ):
                                sent_locs.append(ent)
                            elif ent.value.upper() in ("DATE", "TIME"):
                                sent_times.append(ent)

            event.loc = first(sent_locs, None)
            if event.loc is not None:
                entity = first(event.loc.entities, None)
                if entity is not None:
                    event.loc = entity
                else:
                    event.loc.type = "entity"
                    event.loc.value = "Location"
                    doc.text.attach_annotation(event.loc)

            event.time = first(sent_times, None)
            if event.time is not None:
                entity = first(event.time.entities, None)
                if entity is not None:
                    event.time = entity
                else:
                    event.time.type = "entity"
                    event.time.value = "Time"
                    doc.text.attach_annotation(event.time)

            event.a0 = process_a0_a1(event.a0)
            event.a1 = process_a0_a1(event.a1)
            if event.a1 or event.a0:
                events.append(event)
    return events
