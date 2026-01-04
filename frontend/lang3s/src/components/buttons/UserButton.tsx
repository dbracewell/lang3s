"use client";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LogOutIcon, Moon, Sun, User2Icon } from "lucide-react";
import * as React from "react";
import { useState } from "react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { authClient } from "@/lib/auth/auth-client";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { logout } from "@/features/auth/helpers";

export const UserButton = ({
  children,
  align,
  showArrow = true,
  ref,
}: {
  children: React.ReactNode;
  align?: "center" | "start" | "end";
  showArrow?: boolean;
  ref?: React.Ref<HTMLDivElement>;
}) => {
  const { setTheme } = useTheme();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger className="outline-0">
        {children}
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} ref={ref}>
        <DropdownMenuGroup>
          {showArrow && <div className="dropdown-arrow left-[82%]!"></div>}
          <DropdownMenuItem asChild>
            <Link href={"/account"}>
              <User2Icon /> Account
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => logout(() => router.push("/"))}>
            <LogOutIcon />
            Logout
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <div className="my-1 flex w-full items-center justify-center rounded-full">
            <button
              type="button"
              className="bg-accent text-accent-foreground dark:hover:bg-accent/50 flex w-1/2 items-center justify-center rounded-full rounded-r-none border border-r-0 p-1 px-2 dark:cursor-pointer dark:bg-transparent"
              onClick={() => {
                setTheme("light");
                setOpen(false);
              }}
            >
              <Sun className="size-4" />
            </button>
            <button
              type="button"
              className="dark:bg-accent hover:bg-accent/50 flex w-1/2 cursor-pointer items-center justify-center rounded-full rounded-l-none border border-l-0 bg-transparent p-1 px-2 transition-all dark:cursor-default"
              onClick={() => {
                setTheme("dark");
                setOpen(false);
              }}
            >
              <Moon className="size-4" />
            </button>
          </div>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
