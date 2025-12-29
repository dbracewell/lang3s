import z from "zod";

export type TextAnnotationProps = {
  id: string;
  text: string;
  start: number;
  end: number;
  type: string;
  value: string;
  color?: string;
  metadata: Record<string, unknown>;
};

export const Lang3sFile = z.object({
  path: z.string().nullish(),
  mime_type: z.string(),
  content: z.string(),
  encoding: z.string().nullish(),
  metadata: z.record(z.string(), z.any()).default({}).optional(),
});

export class Lang3sTextAnnotation {
  id: string;
  text: string;
  start: number;
  end: number;
  type: string;
  value: string;
  color: string;
  metadata: Record<string, unknown> = {};
  textObject: Lang3sText | undefined = undefined;

  constructor({
    id,
    text,
    start,
    end,
    type,
    value,
    metadata,
    color,
  }: TextAnnotationProps) {
    this.id = id;
    this.text = text;
    this.start = start;
    this.end = end;
    this.type = type;
    this.value = value;
    this.metadata = metadata;
    this.color = color ?? "SLATE";
  }

  protected setTextObject = (textObject: Lang3sText) => {
    this.textObject = textObject;
  };

  getCorefChain = () => {
    const id = this.COREF().id;
    return (
      this.textObject?.annotations.filter(
        (annotation: Lang3sTextAnnotation) =>
          annotation.COREF().id === id && annotation.id !== this.id,
      ) ?? []
    );
  };

  A0 = () => {
    return ((this.metadata["A0"] as string[]) ?? []).map(
      (a) => this.textObject!.id2Annotation[a],
    );
  };

  A1 = () => {
    return ((this.metadata["A1"] as string[]) ?? []).map(
      (a) => this.textObject!.id2Annotation[a],
    );
  };

  TIME = () => {
    if (this.metadata["TIME"] != null) {
      return this.textObject!.id2Annotation[this.metadata["TIME"] as string];
    }
    return null;
  };

  LOC = () => {
    if (this.metadata["LOC"] != null) {
      return this.textObject!.id2Annotation[this.metadata["LOC"] as string];
    }
    return null;
  };

  COREF = () => {
    if (this.metadata["coref"] != null) {
      return this.textObject!.id2Annotation[this.metadata["coref"] as string];
    }
    return this;
  };

  overlaps = (other: Lang3sTextAnnotation) => {
    return this.end > other.start && this.start < other.end;
  };

  tokens(): Lang3sTextAnnotation[] {
    return this.textObject!.tokens.slice(this.start, this.end);
  }

  sentences(): Lang3sTextAnnotation[] {
    return this.textObject!.sentences.filter((s) => s.overlaps(this));
  }

  annotations(type: string): Lang3sTextAnnotation[] {
    return this.textObject!.annotations.filter(
      (s) =>
        (type.startsWith("ALL") ? s.value.startsWith(type) : s.type === type) &&
        s.overlaps(this),
    );
  }

  interleave(types: string[]): Lang3sTextAnnotation[] {
    const toReturn: Lang3sTextAnnotation[] = [];

    const tokens = this.tokens()
      .map((token) => token)
      .sort((a, b) => a.start - b.start);

    const annotations = types
      .flatMap((type) => this.annotations(type))
      .sort((a, b) =>
        a.start === b.start ? b.end - a.end : a.start - b.start,
      );

    let ti = 0;
    let ai = 0;
    const na = annotations.length;
    const nt = tokens.length;
    let lastEnd = -1;

    while (ti < nt || ai < na) {
      if (ai >= na) {
        tokens.slice(ti, nt).forEach((t) => toReturn.push(t));
        break;
      }
      const token = tokens[ti];
      const annotation = annotations[ai];
      if (annotation.start < lastEnd) {
        ai++;
        continue;
      }
      if (annotation.start <= token.start) {
        toReturn.push(annotation);
        ai += 1;
        while (ti < nt && tokens[ti].start < annotation.end) {
          ti += 1;
        }
        lastEnd = annotation.end;
      } else {
        toReturn.push(token);
        ti += 1;
        lastEnd = token.end;
      }
    }
    return toReturn;
  }

  public toString = (): string => {
    return this.text;
  };

  public static create = ({
    id,
    text,
    start,
    end,
    type,
    value,
    metadata,
    textObject,
    color,
  }: TextAnnotationProps & {
    textObject: Lang3sText;
  }): Lang3sTextAnnotation => {
    const annotation = new Lang3sTextAnnotation({
      id,
      text,
      start,
      end,
      type,
      value,
      metadata,
      color,
    });
    annotation.setTextObject(textObject);
    return annotation;
  };
}

export class Lang3sText {
  id: string;
  tokens: Lang3sTextAnnotation[];
  sentences: Lang3sTextAnnotation[];
  annotations: Lang3sTextAnnotation[];
  id2Annotation: Record<string, Lang3sTextAnnotation>;
  text: string;

  constructor({
    id,
    text,
    annotations,
  }: {
    id: string;
    text: string;
    annotations: TextAnnotationProps[];
  }) {
    this.id = id;
    this.text = text;
    this.tokens = [];
    this.sentences = [];
    this.annotations = [];
    this.id2Annotation = {};

    for (const a of annotations) {
      const lang3sAnnotation = Lang3sTextAnnotation.create({
        ...a,
        textObject: this,
      });
      this.id2Annotation[lang3sAnnotation.id] = lang3sAnnotation;
      switch (a.type) {
        case "token":
          this.tokens.push(lang3sAnnotation);
          break;

        case "sentence":
          this.sentences.push(lang3sAnnotation);
          break;

        default:
          this.annotations.push(lang3sAnnotation);
      }
    }
    this.tokens = this.tokens.sort((a, b) => a.start - b.start);
    this.sentences = this.sentences.sort((a, b) => a.start - b.start);
    this.annotations = this.annotations.sort((a, b) =>
      a.start === b.start ? -(a.end - b.end) : a.start - b.start,
    );
  }

  annotationsByType(type: string) {
    return this.annotations.filter((a) => a.type === type);
  }

  public toString = (): string => {
    return this.text;
  };
}

export class Lan3gsDocument {
  id: string;
  metadata: Record<string, string>;
  text?: Lang3sText;

  constructor({
    id,
    metadata,
    text,
  }: {
    id: string;
    metadata: Record<string, string>;
    text: {
      id: string;
      text: string;
      annotations: TextAnnotationProps[];
    };
  }) {
    this.id = id;
    this.metadata = metadata;
    this.text = new Lang3sText({
      id: text.id,
      text: text.text,
      annotations: text.annotations,
    });
  }

  public toString = (): string => {
    return `Document(${this.id})`;
  };
}
