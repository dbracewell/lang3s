"use client";
import { CheckIcon, ChevronRightIcon, NetworkIcon } from "lucide-react";
import React, {
  createContext,
  Dispatch,
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils/cn";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { ONTOLOGY_ROOT } from "@/features/common/constants";
import { useQuery } from "@tanstack/react-query";
import { ontologyGetOptions } from "@/clients/core/@tanstack/react-query.gen";
import { coreClient } from "@/lib/api";
import {
  IsolatedOntologyEntry,
  OntologyFrontEnd,
  OntologyMapping,
  OntologyProperty,
} from "@/clients/core";

const getBreadCrumbPart = (
  value: string,
  index: number,
  crumbs: string[],
  maxBreadcrumbs: number,
  setTop: (value: string) => void,
) => {
  const length = crumbs.length;

  if (index + 1 === length) {
    return <span>{value}</span>;
  }

  if (length >= maxBreadcrumbs && index === 1) {
    return (
      <>
        ... <ChevronRightIcon className="size-3" />
      </>
    );
  }

  if (length >= maxBreadcrumbs && index > length - 2) {
    return <></>;
  }

  return (
    <>
      <button
        type="button"
        className="link"
        onClick={() => setTop(crumbs.slice(0, index + 1).join("."))}
      >
        {value}
      </button>
      {index + 1 < length && <ChevronRightIcon className="size-3" />}
    </>
  );
};

type OntNode = IsolatedOntologyEntry & {
  hasChildren: boolean;
};

type OntologyInfo = {
  ontology?: OntologyFrontEnd;
  breadcrumbs: string[];
  rootNode: string;
  current: string;
  currentNode?: IsolatedOntologyEntry;
  checkedNodes: string[];
  setCheckedNodes?: Dispatch<React.SetStateAction<string[]>>;
  setCurrent: (value: string) => void;
  sections: OntNode[][];
};

export const OntologyContext = createContext<OntologyInfo>({
  breadcrumbs: [],
  rootNode: ONTOLOGY_ROOT,
  current: "",
  setCurrent: () => {},
  sections: [],
  checkedNodes: [],
});

export const useOntology = (): OntologyInfo => {
  const ontology = React.useContext(OntologyContext);
  if (ontology == null) {
    throw new Error("useOntology must be used within an OntologyProvider");
  }
  return ontology;
};

const Provider = ({
  rootNode = ONTOLOGY_ROOT,
  selectedNode,
  children,
  checkedNodes,
  setCheckedNodes,
}: {
  rootNode?: string;
  selectedNode?: string;
  isSelector?: boolean;
  children: React.ReactNode;
  checkedNodes?: string[];
  setCheckedNodes?: Dispatch<React.SetStateAction<string[]>>;
}) => {
  const { data: ontology, isPending } = useQuery({
    ...ontologyGetOptions({
      client: coreClient,
    }),
  });
  const [current, setCurrent] = useState(selectedNode ?? rootNode);

  const validPaths = useMemo(() => {
    if (ontology) {
      return new Set(ontology.paths);
    }
    return new Set();
  }, [ontology]);

  useEffect(() => {
    if (!ontology || !checkedNodes || !setCheckedNodes) return;
    const filteredNodes = checkedNodes.filter((path) => validPaths.has(path));

    if (filteredNodes.length !== checkedNodes.length) {
      setCheckedNodes(filteredNodes);
    }
  }, [ontology, checkedNodes, setCheckedNodes, validPaths]);

  const currentNode = useMemo(() => {
    if (ontology == null) return undefined;
    if (current === rootNode) {
      return ontology.nodes[rootNode]!;
    }
    return ontology.nodes[current]!;
  }, [current, ontology, rootNode]);

  const breadcrumbs = useMemo(() => {
    if (ontology == null) return [];
    if (!ontology.nodes[current]) return [rootNode];
    const parts = current.split(".");
    const topIndex = parts.findIndex((n) => n === rootNode);
    return parts.slice(topIndex);
  }, [current, rootNode, ontology]);

  const sections = useMemo(() => {
    if (ontology == null) {
      return [];
    }

    const ALL_NODE = ontology.nodes[rootNode]!.id;
    const firstSection = Object.values(ontology.nodes)
      .filter((o) => o.parent_id === ALL_NODE)
      .map((o) => ({
        ...o,
        hasChildren:
          Object.values(ontology.nodes).filter((c) => c.parent_id === o.id)
            .length > 0,
      }))
      .sort((a, b) => a.path.localeCompare(b.path));

    const sections = [firstSection];

    if (current === rootNode) {
      return sections;
    }

    const parts = current.split(".").slice(1);
    for (let currentPart of parts) {
      const lastPart = sections[sections.length - 1].filter(
        (o) => o.name === currentPart,
      );
      if (lastPart.length === 0) {
        continue;
      }
      const lastId = lastPart[0].id;
      const children = Object.values(ontology.nodes)
        .filter((o) => o.parent_id === lastId)
        .map((o) => ({
          ...o,
          hasChildren:
            Object.values(ontology.nodes).filter((c) => c.parent_id === o.id)
              .length > 0,
        }));
      if (children.length > 0) {
        sections.push(children.sort((a, b) => a.path.localeCompare(b.path)));
      }
    }
    return sections;
  }, [current, ontology, rootNode]);

  const finalCheckedNodes = checkedNodes ?? [];
  const value: OntologyInfo = {
    current,
    setCurrent,
    breadcrumbs,
    ontology: ontology,
    checkedNodes: finalCheckedNodes,
    setCheckedNodes,
    sections,
    currentNode,
    rootNode,
  };

  if (isPending) {
    return <Spinner />;
  }

  return (
    <OntologyContext.Provider value={value}>
      {children}
    </OntologyContext.Provider>
  );
};

const Container = ({
  children,
  className,
  orientation = "vertical",
}: {
  rootNode?: string;
  children: React.ReactNode;
  isSelector?: boolean;
  checkedNodes?: string[];
  className?: string;
  orientation?: "horizontal" | "vertical";
  setCheckedNodes?: Dispatch<React.SetStateAction<string[]>>;
}) => {
  return (
    <div
      className={cn(
        "flex h-full min-h-0 w-full min-w-0 flex-1 justify-between gap-2 overflow-hidden",
        className,
        orientation === "horizontal" ? "flex-row!" : "flex-col!",
      )}
    >
      {children}
    </div>
  );
};

const BreadCrumbs = ({ maxBreadcrumbs = 4 }: { maxBreadcrumbs?: number }) => {
  const { breadcrumbs, setCurrent } = useOntology();
  return (
    <div className="bg-muted text-muted-foreground scrollable flex min-w-full items-center gap-2 overflow-x-auto rounded border p-2 text-xs">
      <SelectorSearch />
      {breadcrumbs.map((c, i) => (
        <Fragment key={i}>
          {getBreadCrumbPart(c, i, breadcrumbs, maxBreadcrumbs, setCurrent)}
        </Fragment>
      ))}
    </div>
  );
};

const SelectorSectionEntryCheckbox = ({
  o,
}: {
  o: IsolatedOntologyEntry & {
    hasChildren: boolean;
  };
}) => {
  const { checkedNodes, setCheckedNodes } = useOntology();
  if (checkedNodes == null || setCheckedNodes == null) {
    return null;
  }
  return (
    <Checkbox
      className="size-4"
      checked={!!checkedNodes.find((p) => o.path.startsWith(p))}
      disabled={
        !!checkedNodes.find((p) => o.path.startsWith(p) && o.path !== p)
      }
      onCheckedChange={(checked) => {
        if (!!checked) {
          setCheckedNodes((prev) =>
            !!prev.find((p) => o.path.startsWith(p))
              ? prev
              : [...prev.filter((p) => !p.startsWith(o.path)), o.path],
          );
        } else {
          setCheckedNodes((prev) => prev.filter((n) => n !== o.path));
        }
      }}
    />
  );
};

const SectionSelectAll = ({
  section,
  index,
}: {
  index: number;
  section: { path: string }[];
}) => {
  const { checkedNodes, setCheckedNodes } = useOntology();

  const isParentChecked = useMemo(() => {
    return section.some(
      (o) => !!checkedNodes.find((p) => o.path.startsWith(p) && o.path !== p),
    );
  }, [checkedNodes, section]);

  const areAllChecked = useMemo(() => {
    return (
      section.filter((o) => !!checkedNodes.find((p) => o.path.startsWith(p)))
        .length === section.length
    );
  }, [checkedNodes, section]);

  if (checkedNodes == null || setCheckedNodes == null) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex items-center gap-2 border-b border-dashed bg-zinc-300 px-2 py-1.5 dark:bg-zinc-950",
        areAllChecked && "bg-heading dark:bg-heading text-white",
      )}
    >
      <Checkbox
        id={`section-${index}-select-all`}
        checked={areAllChecked}
        disabled={isParentChecked}
        onCheckedChange={(checked) => {
          if (!!checked) {
            setCheckedNodes((prev) => {
              const toKeep = prev.filter(
                (p) => !section.some((o) => p.startsWith(o.path)),
              );
              return [...toKeep, ...section.map((o) => o.path)];
            });
          } else {
            setCheckedNodes((prev) =>
              prev.filter((n) => !section.some((p) => p.path === n)),
            );
          }
        }}
      />{" "}
      <Label htmlFor={`section-${index}-select-all`} className="text-xs">
        Select All
      </Label>
    </div>
  );
};

const isSelected = (path: string, checkedNodes?: string[]) => {
  if (checkedNodes == null || checkedNodes.length === 0) {
    return false;
  }
  return checkedNodes.some((p) => path.startsWith(p) || p.startsWith(path));
};

const SelectionSummary = () => {
  const { checkedNodes, ontology } = useOntology();
  if (checkedNodes == null || checkedNodes.length == 0) {
    return null;
  }
  const selected = Object.values(ontology?.nodes ?? {}).filter((o) =>
    checkedNodes.some((c) => o.path.startsWith(c)),
  ).length;
  return (
    <div className="bg-accent text-accent-foreground rounded border border-dashed p-1 text-xs">
      {selected} Selected
    </div>
  );
};

export type Section = {
  hasChildren: boolean;
  id?: number;
  name: string;
  path: string;
  description: string;
  color: string;
  parent_id?: number;
  mappings?: Array<OntologyMapping>;
  properties?: {
    [p: string]: OntologyProperty;
  };
}[];

const Sections = ({
  className,
  sectionHeader,
  sectionFooter,
  entryAlternativeNextButton,
  entryToolButtons,
  sectionWidth,
}: {
  className?: string;
  sectionHeader?: (section: Section) => React.ReactNode;
  sectionFooter?: (section: Section) => React.ReactNode;
  entryToolButtons?: ((item: Section[number]) => React.ReactNode)[];
  entryAlternativeNextButton?: (item: Section[number]) => React.ReactNode;
  sectionWidth?: number;
}) => {
  const { sections, current, setCurrent, breadcrumbs, checkedNodes } =
    useOntology();
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => endRef.current?.scrollIntoView(), [current]);
  return (
    <div className="scrollable flex h-full flex-1 flex-col gap-2 overflow-auto">
      <div className="flex w-fit flex-1 gap-1.5">
        {sections.map((section, i) => (
          <div className="flex flex-col" key={i}>
            <div
              className="bg-card flex h-full w-50 flex-col rounded border"
              style={{
                width: sectionWidth ? `${sectionWidth}px` : undefined,
              }}
            >
              <SectionSelectAll section={section} index={i} />
              {sectionHeader?.(section)}
              <div className="scrollable h-full overflow-x-auto">
                <div className="w-fit min-w-full">
                  {section.map((o) => (
                    <div
                      key={o.name}
                      className={cn(
                        "flex w-full cursor-pointer items-center gap-2 divide-y border-b p-2 text-sm whitespace-nowrap",
                        className,
                        !!breadcrumbs.find((p) => o.name === p)
                          ? "bg-accent!"
                          : isSelected(o.path, checkedNodes)
                            ? "bg-accent/40!"
                            : "hover:bg-accent/20",
                      )}
                    >
                      <SelectorSectionEntryCheckbox o={o} />
                      <div
                        className="flex flex-1 items-center justify-between"
                        onClick={() => {
                          setCurrent(o.path);
                        }}
                      >
                        <h2>{o.name}</h2>
                        <div className="flex items-center gap-2">
                          {entryToolButtons?.map((fn, i) => (
                            <Fragment key={i}>{fn(o)}</Fragment>
                          ))}
                          {o.hasChildren ? (
                            <div className="px-1">
                              <ChevronRightIcon className="size-4" />
                            </div>
                          ) : (
                            entryAlternativeNextButton?.(o)
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {sectionFooter?.(section)}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
};

const SelectorSearch = () => {
  const { ontology, setCurrent, rootNode, checkedNodes } = useOntology();
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="icon-xs"
          role="combobox"
          type="button"
          aria-expanded={open}
        >
          <NetworkIcon />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-50 p-0 sm:w-125" align="start">
        <Command>
          <CommandInput placeholder="Search for concept..." />
          <CommandList className="w-full">
            <CommandEmpty>Nothing found.</CommandEmpty>
            <CommandGroup>
              {Object.values(ontology?.nodes ?? {})
                .filter(
                  (o) => o.path.startsWith(rootNode) && o.path !== rootNode,
                )
                .map((o) => (
                  <CommandItem
                    key={o.path}
                    value={o.path}
                    className="flex items-center justify-between gap-2"
                    onSelect={() => {
                      setCurrent(o.path);
                      setOpen(false);
                    }}
                  >
                    <div className="flex-1 truncate">
                      {o.path.split(".").slice(1).join(" > ")}
                    </div>
                    {checkedNodes &&
                      checkedNodes.find((n) => o.path.startsWith(n)) && (
                        <CheckIcon />
                      )}
                  </CommandItem>
                ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

const SelectedInformation = ({
  className,
  children,
  showPath = true,
  showName = true,
}: {
  className?: string;
  showPath?: boolean;
  showName?: boolean;
  children?: React.ReactNode;
}) => {
  const { currentNode } = useOntology();
  if (currentNode == null) {
    return (
      <div
        className={cn(
          "flex h-full! w-50 gap-1 rounded-lg border bg-slate-100 p-2 dark:bg-slate-950/50",
          className,
        )}
      />
    );
  }

  return (
    <div
      className={cn(
        "flex w-50 flex-col gap-2 rounded-lg border bg-slate-100 p-2 dark:bg-slate-950/50",
        className,
      )}
    >
      <div
        className={cn(
          "flex w-full flex-col gap-3",
          children && "border-b pb-1",
        )}
      >
        {showName && (
          <h3 className="truncate border-b pb-1 text-2xl font-bold">
            {currentNode.name}
          </h3>
        )}
        <div className="flex flex-col gap-1">
          {showPath && (
            <div className="flex w-full items-center gap-1 truncate text-sm">
              <h4 className="font-medium">Path</h4>
              <p className="truncate">
                {currentNode.path.split(".").join(" > ")}
              </p>
            </div>
          )}
          <div className="flex w-full items-center gap-1 text-sm">
            <h4 className="font-medium">Description:</h4>
            <p className="truncate">
              {!!currentNode.description
                ? currentNode.description
                : "Not defined"}
            </p>
          </div>
        </div>
      </div>
      {children}
    </div>
  );
};

export const OntologySelector = {
  Provider,
  Container,
  BreadCrumbs,
  Sections,
  SelectionSummary,
  SelectedInformation,
};
