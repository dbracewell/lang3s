import { DocumentSchema, TextAnnotationSchema } from "@/lib/nlp/schemas";
import z from "zod";

export type TextAnnotationProps = z.infer<typeof TextAnnotationSchema> & {
  color?: string;
};

export class Lang3sTextAnnotation {
  id: string;
  content: string;
  start: number;
  end: number;
  type: string;
  value: string;
  color: string;
  metadata_json: Record<string, unknown> = {};
  textObject: Lang3sText | undefined = undefined;

  constructor({
    id,
    content,
    start,
    end,
    type_,
    value,
    metadata_json,
    color,
  }: TextAnnotationProps) {
    this.id = id;
    this.content = content;
    this.start = start;
    this.end = end;
    this.type = type_;
    this.value = value;
    this.metadata_json = metadata_json;
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
    return ((this.metadata_json["A0"] as string[]) ?? []).map(
      (a) => this.textObject!.id2Annotation[a],
    );
  };

  A1 = () => {
    return ((this.metadata_json["A1"] as string[]) ?? []).map(
      (a) => this.textObject!.id2Annotation[a],
    );
  };

  TIME = () => {
    if (this.metadata_json["TIME"] != null) {
      return this.textObject!.id2Annotation[
        this.metadata_json["TIME"] as string
      ];
    }
    return null;
  };

  LOC = () => {
    if (this.metadata_json["LOC"] != null) {
      return this.textObject!.id2Annotation[
        this.metadata_json["LOC"] as string
      ];
    }
    return null;
  };

  COREF = () => {
    if (this.metadata_json["coref"] != null) {
      return this.textObject!.id2Annotation[
        this.metadata_json["coref"] as string
      ];
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
    const numAnnotations = annotations.length;
    const numTokens = tokens.length;
    let lastEnd = -1;

    while (ti < numTokens || ai < numAnnotations) {
      if (ai >= numAnnotations) {
        tokens.slice(ti, numTokens).forEach((t) => toReturn.push(t));
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
        while (ai < numAnnotations && annotations[ai].start < annotation.end) {
          ai += 1;
        }
        while (ti < numTokens && tokens[ti].start < annotation.end) {
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
    return this.content;
  };

  public static create = ({
    textObject,
    ...props
  }: z.infer<typeof TextAnnotationSchema> & {
    textObject: Lang3sText;
    color?: string;
  }): Lang3sTextAnnotation => {
    const annotation = new Lang3sTextAnnotation({ ...props });
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
  content: string;

  constructor({
    id,
    content,
    annotations,
  }: {
    id: string;
    content: string;
    annotations: z.infer<typeof TextAnnotationSchema>[];
  }) {
    this.id = id;
    this.content = content;
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
      switch (a.type_) {
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
    return this.content;
  };
}

export class Lan3gsDocument {
  id: string;
  metadata_json: Record<string, string>;
  text?: Lang3sText;

  constructor(data: z.infer<typeof DocumentSchema>) {
    this.id = data.id;
    this.metadata_json = data.metadata_json;
    this.text = new Lang3sText({
      id: data.text.id,
      content: data.text.content,
      annotations: data.text.annotations,
    });
  }

  public toString = (): string => {
    return `Document(${this.id})`;
  };
}
