"use client";
import React, { useEffect, useState } from "react";
import { NavSidebar } from "@/components/main-layout/NavSidebar";
import { MenuBar } from "@/components/main-layout/MenuBar";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { cn } from "@/lib/utils/cn";
import { ChatWindow } from "@/features/chat/ui/components/ChatWindow";
import { useChatWindowStatus } from "@/features/chat/hooks/useChatWindowStatus";
import { useChatContext } from "@/features/chat/hooks/useChatContext";
import { usePathname } from "next/navigation";

export const Wrapper = ({ children }: { children: React.ReactNode }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const pathname = usePathname();
  const { open } = useChatWindowStatus();
  const { setContext } = useChatContext();
  useEffect(() => setContext(""), [pathname]);
  return (
    <>
      <NavSidebar isOpen={isMenuOpen} setIsOpen={setIsMenuOpen} />
      <div className="from-sidebar-light to-sidebar-dark flex h-screen w-screen flex-col overflow-hidden bg-linear-to-b">
        <MenuBar setIsMenuOpen={setIsMenuOpen} />
        <div className="min-h-0 flex-1 overflow-hidden p-1 pt-0!">
          <div className="bg-background inset-shadow-insert-shadow-border flex h-full min-h-0 w-full flex-col rounded-b-2xl border p-2 inset-shadow-xs">
            <ResizablePanelGroup
              direction="horizontal"
              className="min-h-0 w-full flex-1"
            >
              <ResizablePanel
                className={cn(
                  "@container flex min-h-0 flex-1 flex-col",
                  open && "pr-2",
                )}
                defaultSize={open ? 75 : 100}
              >
                {children}
              </ResizablePanel>
              {open && (
                <>
                  <ResizableHandle />
                  <ResizablePanel
                    defaultSize={25}
                    maxSize={40}
                    id="chat-panel"
                    order={2}
                  >
                    <ChatWindow />
                  </ResizablePanel>
                </>
              )}
            </ResizablePanelGroup>
          </div>
        </div>
      </div>
    </>
  );
};
