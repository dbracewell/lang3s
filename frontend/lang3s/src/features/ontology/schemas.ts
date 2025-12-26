import z from "zod";

export const OntologyConceptSchema = z.object({
  parentId: z.number(),
  name: z.string().regex(/^[a-zA-Z_0-9]{4,20}$/, {
    message:
      "Concept names must be between 4 to 20 characters long and only consist of letters, digits, or underscore",
  }),
  description: z.string().optional(),
});
