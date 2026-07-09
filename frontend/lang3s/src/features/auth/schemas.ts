import z from "zod";
import { UserRoles } from "@/lib/auth/permissions";

export const UserAccountSchema = z.object({
  name: z.string().trim().min(1, "Name is required"),
  email: z.email(),
  username: z
    .string()
    .trim()
    .min(1, "Username is required.")
    .regex(
      /^[a-zA-Z0-9_]{4,15}$/,
      "Username must only contain letters, digits, and underscores and must be between 4 and 15 characters long",
    ),
  password: z
    .string()
    .trim()
    .min(8, "Passwords must be between 8 and 16 characters")
    .max(16, "Passwords must be between 8 and 16 characters")
    .refine(
      (data) => /[a-z]/i.test(data),
      "Must contain at least 1 lower case letter",
    )
    .refine(
      (data) => /[A-Z]/i.test(data),
      "Must contain at least 1 upper case letter",
    )
    .refine((data) => /\d/i.test(data), "Must contain at least 1 digit")
    .refine(
      (data) => /[!@#$%^&*]/i.test(data),
      "Must contain at least 1 special character !@#$%^&*",
    ),
  role: z.enum(UserRoles),
});

export type UserAccountSchemaType = z.infer<typeof UserAccountSchema>;

export const UserAccountEditSchema = z.object({
  userId: z.string(),
  role: z.string(),
  isActive: z.boolean(),
});

export type UserAccountEditSchemaType = z.infer<typeof UserAccountEditSchema>;

export const AdminAccountSchema = UserAccountSchema.extend({
  passphrase: z.string().trim().min(1, "Administrator passphrase is required"),
});

export type AdminAccountSchemaType = z.infer<typeof AdminAccountSchema>;
