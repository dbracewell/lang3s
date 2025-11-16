from typing import List, Optional
from .text_annotation import TextAnnotation


class Event:
    def __init__(
        self,
        trigger: TextAnnotation,
        a0: Optional[List[TextAnnotation]] = None,
        a1: Optional[List[TextAnnotation]] = None,
        time: Optional[TextAnnotation] = None,
        loc: Optional[TextAnnotation] = None,
    ) -> None:
        self.trigger = trigger
        self.A0: List[TextAnnotation] = a0 or []
        self.A1: List[TextAnnotation] = a1 or []
        self.TIME: Optional[TextAnnotation] = time
        self.LOC: Optional[TextAnnotation] = loc

    def __str__(self) -> str:
        out_a0 = [
            f"{a0.text}"
            if a0.coref is None or a0.coref == a0
            else f"{a0.text} ({a0.coref.text})"
            for a0 in self.A0
        ]
        out_a1 = [
            f"{a1.text}"
            if a1.coref is None or a1.coref == a1
            else f"{a1.text} ({a1.coref.text})"
            for a1 in self.A1
        ]
        out_time = self.TIME
        if self.TIME is not None and self.TIME.coref != self.TIME:
            out_time = f"{self.TIME.text} ({self.TIME.coref.text})"
        out_loc = self.LOC
        if self.LOC is not None and self.LOC.coref != self.LOC:
            out_loc = f"{self.LOC.text} ({self.LOC.coref.text})"
        return f"Event(value='{self.trigger.value}', trigger='{self.trigger}', A0={out_a0}, A1={out_a1}, TIME={out_time},LOC={out_loc})"

    def __repr__(self) -> str:
        return str(self)
