from __future__ import annotations

from typing import TYPE_CHECKING

from lang3s.data.schemas import Metadata

if TYPE_CHECKING:
    from lang3s.data.schemas import Document


def extract_events_for_doc(doc: Document):


    from .event_extraction import extract_events

    events = extract_events(doc)
    for event in events:
        if len(event.a0) == 0 and len(event.a1) == 0:
            continue

        doc.text.add_annotation(
            content=event.trigger.content,
            start=event.trigger.start,
            end=event.trigger.end,
            sentence_index=event.trigger.sentence_index,
            type_=event.trigger.type_,
            value=event.trigger.value,
            source="rb_event_extractor",
            metadata_json={
                Metadata.LEMMA: event.trigger.lemma,
                Metadata.A0: [a0.id for a0 in event.a0],
                Metadata.A0_TEXT: [a0.content.upper() for a0 in event.a0],
                Metadata.A0_COREF_TEXT: [a0.normalized for a0 in event.a0],
                Metadata.A1: [a1.id for a1 in event.a1],
                Metadata.A1_TEXT: [a1.content.upper() for a1 in event.a1],
                Metadata.A1_COREF_TEXT: [a1.normalized for a1 in event.a1],
                Metadata.TIME: event.time.id if event.time is not None else None,
                Metadata.LOC: event.loc.id if event.loc is not None else None,
                Metadata.TIME_TEXT: event.time.content.upper()
                if event.time is not None
                else None,
                Metadata.TIME_COREF_TEXT: event.time.normalized.upper()
                if event.time is not None
                else None,
                Metadata.LOC_TEXT: event.loc.normalized
                if event.loc is not None
                else None,
                Metadata.LOC_COREF_TEXT: event.loc.normalized
                if event.loc is not None
                else None,
            },
        )
