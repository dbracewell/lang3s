import {
  createContext,
  ReactNode,
  RefObject,
  useContext,
  useState,
} from "react";
import { ForceGraphPoint } from "@/components/d3/ForceGraph/types";
import { RefContextType } from "@/components/d3/types";
import { useRegistry } from "@/components/d3/hooks";

type D3ContextType<ElementType> = RefContextType & {
  hoveredNode: ElementType | null;
  setHoveredNode: (hovered: ElementType | null) => void;
};

const D3Context = createContext<D3ContextType<any> | undefined>(undefined);

export const D3ContextProvider = <ElementType,>({
  children,
  externalRefs,
}: {
  children: ReactNode;
  externalRefs?: Record<string, RefObject<any | null>>;
}) => {
  const [hoveredNode, setHoveredNode] = useState<ElementType | null>(null);
  const { getRef, registerRef } = useRegistry({ externalRefs });

  const value: D3ContextType<ElementType> = {
    registerRef,
    getRef,
    hoveredNode,
    setHoveredNode,
  };

  return <D3Context.Provider value={value}>{children}</D3Context.Provider>;
};

export const useD3Context = <Point extends ForceGraphPoint>() => {
  const context = useContext(D3Context);

  if (!context) {
    throw new Error("useD3Context must be used within a D3ContextProvider");
  }

  return context as D3ContextType<Point>;
};
