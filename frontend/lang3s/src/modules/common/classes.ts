import z from "zod";

export type TextAnnotationProps = {
  id: string;
  text: string;
  start: number;
  end: number;
  type: string;
  value: string;
};

export const Lang3sFile = z.object({
  path: z.string(),
  mime_type: z.string(),
  content: z.string(),
  encoding: z.string().nullish(),
  metadata: z.record(z.string(), z.string()).default({}).optional(),
});
export type Lang3sFileType = z.infer<typeof Lang3sFile>;

export type TextAnnotationDB = {
  type: string;
  annotations: TextAnnotationProps[];
};

export class Lang3sTextAnnotation {
  id: string;
  text: string;
  start: number;
  end: number;
  type: string;
  value: string;
  textObject: Lang3sText | undefined = undefined;

  constructor({ id, text, start, end, type, value }: TextAnnotationProps) {
    this.id = id;
    this.text = text;
    this.start = start;
    this.end = end;
    this.type = type;
    this.value = value;
  }

  protected setTextObject = (textObject: Lang3sText) => {
    this.textObject = textObject;
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
      (s) => s.type === type && s.overlaps(this),
    );
  }

  interleave(types: string[]): Lang3sTextAnnotation[] {
    const toReturn: Lang3sTextAnnotation[] = [];
    const annotations = types
      .flatMap((type) => this.annotations(type))
      .concat(this.tokens())
      .sort((a, b) =>
        a.start === b.start ? b.end - a.end : a.start - b.start,
      );

    let i = this.start;
    let ai = 0;
    while (ai < annotations.length) {
      const maxAnnotation = annotations[ai];
      toReturn.push(maxAnnotation);
      i = maxAnnotation.end;
      ai++;
      while (
        ai < annotations.length &&
        annotations[ai].overlaps(maxAnnotation)
      ) {
        ai++;
      }
    }
    return toReturn;
  }

  public toString = (): string => {
    return this.text;
  };

  toJSON = () => {
    return {
      start: this.start,
      end: this.end,
      type: this.type,
      value: this.value,
      text: this.text,
    };
  };

  public static create = ({
    id,
    text,
    start,
    end,
    type,
    value,
    textObject,
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
  text: string;

  constructor({
    id,
    text,
    annotations,
  }: {
    id: string;
    text: string;
    annotations: TextAnnotationDB[];
  }) {
    this.id = id;
    this.text = text;
    const annotationsGrouped: Record<string, TextAnnotationProps[]> = {};
    for (const a of annotations) {
      annotationsGrouped[a.type] = a.annotations;
    }
    this.tokens = annotationsGrouped["token"]
      .map((a) => Lang3sTextAnnotation.create({ ...a, textObject: this }))
      .sort((a, b) => a.start - b.start);
    this.sentences = annotationsGrouped["sentence"]
      .map((a) => Lang3sTextAnnotation.create({ ...a, textObject: this }))
      .sort((a, b) => a.start - b.start);
    this.annotations = Object.entries(annotationsGrouped)
      .filter(([type, _]) => type !== "token" && type !== "sentence")
      .flatMap(([_, annotations]) => annotations)
      .map((a) => Lang3sTextAnnotation.create({ ...a, textObject: this }))
      .sort((a, b) =>
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
    text?: {
      id: string;
      text: string;
      annotations: TextAnnotationDB[];
    };
  }) {
    this.id = id;
    this.metadata = metadata;
    this.text = text
      ? new Lang3sText({
          id: text.id,
          text: text.text,
          annotations: text.annotations,
        })
      : undefined;
  }

  public toString = (): string => {
    return `Document(${this.id})`;
  };
}
