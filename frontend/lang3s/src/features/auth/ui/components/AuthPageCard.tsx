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
    <div className="flex grow flex-col md:grid md:grid-cols-[1.2fr_2fr]">
      <div className="flex bg-radial from-slate-500 to-slate-700 py-5 shadow md:p-0 dark:from-slate-800 dark:to-slate-900">
        <div className="mx-auto flex items-center justify-center gap-2 md:flex-col md:gap-5">
          <div className="hidden md:block">
            <Logo height={128} className="fill-white" />
          </div>
          <div className="block md:hidden">
            <Logo height={40} className="fill-white" />
          </div>
          <div className="mx-auto text-3xl font-bold text-gray-200 md:text-5xl">
            Lang3s
          </div>
        </div>
      </div>
      <div className="bg-background cols item-center grow justify-center p-10">
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
