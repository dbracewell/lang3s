import type { ReactNode } from "react";

declare global {
  type SearchParams = Record<string, string | string[] | undefined>;
  type RouteParams = Record<string, string | string[] | undefined>;

  type PageProps<_Route extends string = string> = {
    params: Promise<RouteParams>;
    searchParams: Promise<SearchParams>;
  };

  type LayoutProps<_Route extends string = string> = {
    children: ReactNode;
    params: Promise<RouteParams>;
  };
}

export {};
