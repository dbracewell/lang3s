"use server";
import { db } from "@/db";
import { user } from "@/db/schema";
import { auth } from "@/lib/auth";
import {
   AdminAccountSchema,
   AdminAccountSchemaType,
} from "@/modules/common/schemas";
import { eq } from "drizzle-orm";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export const createAdminAccount = async (values: AdminAccountSchemaType) => {
   const safeValues = AdminAccountSchema.safeParse(values);
   if (!safeValues.success) {
      return {
         status: 400,
      };
   }
   if (safeValues.data.passphrase != process.env.ADMIN_PASSPHRASE!) {
      return {
         status: 401,
      };
   }

   try {
      const res = await auth.api.signUpEmail({
         body: {
            username: safeValues.data.username,
            name: safeValues.data.name,
            email: safeValues.data.email,
            password: safeValues.data.password,
            displayUsername: safeValues.data.username,
         },
      });
      await db
         .update(user)
         .set({
            role: "admin",
         })
         .where(eq(user.id, res.user.id));
      return { status: 200 };
   } catch (error) {
      return {
         status: 500,
      };
   }
};
