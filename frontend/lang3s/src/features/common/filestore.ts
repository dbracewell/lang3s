import "server-only";
import { t3env } from "@/lib/t3env";
import path from "path";
import zlib from "node:zlib";
import { promises as fs } from "fs";
import { DocumentSchema, Lang3sFile } from "@/features/nlp/schemas";
import z from "zod";
import { decode } from "@msgpack/msgpack";

async function writeGzipStringToFile(dataString: string, filename: string) {
  try {
    const compressedData = zlib.gzipSync(dataString);
    await fs.writeFile(filename, compressedData);
  } catch (err) {
    console.error("An error occurred:", err);
  }
}

export class FileStore {
  basePath: string;

  constructor() {
    this.basePath = t3env.FILESTORE_ROOT;
  }

  async getLang3sDocument(id: string) {
    const filePath = path.join(this.basePath, "documents", `${id}.msgpack`);
    const deserializedData = decode(await fs.readFile(filePath));
    return DocumentSchema.parse(deserializedData);
  }

  async saveAnnotationFile(file: z.infer<typeof Lang3sFile>) {
    const filePath = path.join(
      this.basePath,
      "annotation_files",
      `${file.docId}.json.gz`,
    );

    try {
      await fs.mkdir(path.join(this.basePath, "annotation_files"), {
        recursive: true,
      });
    } catch (error) {}

    await writeGzipStringToFile(JSON.stringify(file), filePath);
    return file.docId;
  }
}

export const fileStore = new FileStore();
