"use server";

import { fileStore } from "@/lib/filestore";

export const loadDocument = async (id: string) => {
  return await fileStore.getLang3sDocument(id);
};
