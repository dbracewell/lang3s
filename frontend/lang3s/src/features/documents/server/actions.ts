"use server";

import { fileStore } from "@/features/common/filestore";

export const loadDocument = async (id: string) => {
  return await fileStore.getLang3sDocument(id);
};
