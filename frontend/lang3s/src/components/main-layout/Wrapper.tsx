"use client";
import "react";
import { useState } from "react";
import { NavSidebar } from "@/components/main-layout/NavSidebar";
import { MenuBar } from "@/components/main-layout/MenuBar";

export const Wrapper = ({ children }: { children: React.ReactNode }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  return (
    <>
      <NavSidebar isOpen={isMenuOpen} setIsOpen={setIsMenuOpen} />
      <div className="from-sidebar-light to-sidebar-dark flex h-screen w-screen flex-col overflow-hidden bg-linear-to-b">
        <MenuBar setIsMenuOpen={setIsMenuOpen} />
        <div className="min-h-0 flex-1 overflow-hidden p-1 pt-0!">
          <div className="bg-background inset-shadow-insert-shadow-border flex h-full min-h-0 w-full flex-col rounded-b-2xl border p-2 inset-shadow-xs">
            {children}
          </div>
        </div>
      </div>
    </>
  );
};
