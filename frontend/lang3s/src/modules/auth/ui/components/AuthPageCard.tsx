"use client";
import { Logo } from "@/components/logo";
import {
   Card,
   CardDescription,
   CardHeader,
   CardTitle,
} from "@/components/ui/card";
import React from "react";

type AuthPageProps = {
   title: string;
   description: string;
   children: React.ReactNode;
};

export const AuthPageCard = ({
   title,
   description,
   children,
}: AuthPageProps) => {
   return (
      <div className="grow flex flex-col md:grid md:grid-cols-[1.2fr_2fr]">
         <div className="flex bg-radial from-slate-500 to-slate-700 shadow py-5 md:p-0">
            <div className="mx-auto flex md:flex-col items-center justify-center gap-2 md:gap-5">
               <div className="hidden md:block">
                  <Logo height={128} className="fill-white" />
               </div>
               <div className="block md:hidden">
                  <Logo height={40} className="fill-white" />
               </div>
               <div className="font-bold text-3xl md:text-5xl text-gray-200 mx-auto">
                  Lang3s
               </div>
            </div>
         </div>
         <div className="bg-background grow cols item-center justify-center p-10">
            <Card className="mx-auto w-full max-w-xl">
               <CardHeader>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{description}</CardDescription>
               </CardHeader>
               {children}
            </Card>
         </div>
      </div>
   );
};
