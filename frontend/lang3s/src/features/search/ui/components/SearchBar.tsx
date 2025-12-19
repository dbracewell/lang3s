"use client";
import { CheckboxFormField } from "@/components/form-controls/checkbox-form-field";
import { NumberInputFormField } from "@/components/form-controls/number-input-form-field";
import {
  SelectFormField,
  SelectOptionItem,
} from "@/components/form-controls/select-form-field";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import { capitalize, formatURL } from "@/lib/utils/formatters";
import { cn } from "@/lib/utils/cn";
import {
  Lang3sSearchParams,
  ParsedSearchParams,
  QueryTypes,
  SearchParamSchema,
} from "@/features/search/params";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { zodResolver } from "@hookform/resolvers/zod";
import { SearchIcon, XIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useQueryStates } from "nuqs";
import { useCallback, useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useClickOutside } from "@/hooks/useClickOutside";

const QueryTypeSelectData = [
  ...QueryTypes.keys().map(
    (v) =>
      ({
        type: "item",
        value: QueryTypes[v],
        node: capitalize(QueryTypes[v]),
      }) as SelectOptionItem,
  ),
];

export const SearchBar = () => {
  const router = useRouter();
  const [searchParams] = useQueryStates(Lang3sSearchParams);
  const [isOptionsOpen, setOptionsOpen] = useState(false);

  const searchBarRef = useRef<HTMLFormElement>(null);
  const sTypeRef = useRef<HTMLDivElement | null>(null);
  const aTypeRef = useRef<HTMLDivElement | null>(null);
  const openRef = useRef<HTMLDivElement | null>(null);

  const closeSearchOptions = (doingSearch: boolean) => {
    setOptionsOpen(false);
    if (!doingSearch) {
      setFormValues();
    }
  };

  useClickOutside([searchBarRef, aTypeRef, sTypeRef, openRef], () => {
    closeSearchOptions(false);
  });

  const { data: annotationTypes } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationTypes.queryOptions(),
  );

  const form = useForm<ParsedSearchParams>({
    resolver: zodResolver(SearchParamSchema),
    defaultValues: {
      ...searchParams,
    },
  });

  const queryType = form.watch("stype");

  const onSubmit = (values: ParsedSearchParams) => {
    router.push(formatURL("/search", { ...values, cursor: 1 }));
    router.refresh();
    closeSearchOptions(true);
  };

  const setFormValues = useCallback(() => {
    form.setValue("q", searchParams.q ?? undefined);
    form.setValue("atype", searchParams.atype);
    form.setValue("stype", searchParams.stype);
    form.setValue("aid", searchParams.aid);
    form.setValue("cursor", searchParams.cursor);
    form.setValue("isStrict", searchParams.isStrict);
  }, [
    form,
    searchParams.q,
    searchParams.atype,
    searchParams.stype,
    searchParams.aid,
    searchParams.cursor,
    searchParams.isStrict,
  ]);

  useEffect(() => {
    setFormValues();
  }, [setFormValues]);

  const query = form.watch("q");

  return (
    <Form {...form}>
      <form
        ref={searchBarRef}
        onSubmit={form.handleSubmit(onSubmit)}
        id="searchBarForm"
        className="group relative z-20 w-full max-w-xs py-1 sm:hidden md:block lg:max-w-sm"
        onFocus={() => setOptionsOpen(true)}
      >
        <InputGroup
          className={cn(
            "text-foreground bg-sidebar-dark/50 dark:border-border hover:shadow-shadow dark:hover:shadow-dodger-blue-900 dark:hover:bg-background h-8 w-full rounded-full hover:shadow-xs",
            !!query && "bg-background! dark:bg-background!",
            isOptionsOpen
              ? "bg-background dark:bg-background hover:bg-background dark:hover:bg-background rounded-none rounded-t-lg border border-b-0 border-slate-800 dark:border-slate-500"
              : "hover:bg-white dark:bg-zinc-700",
          )}
        >
          <FormField
            control={form.control}
            name="q"
            render={({ field }) => {
              return (
                <FormItem className="flex-1">
                  <FormControl>
                    <InputGroupInput
                      placeholder="Search..."
                      value={field.value ?? ""}
                      onChange={(e) => {
                        field.onChange(e);
                        form.setValue("aid", null);
                      }}
                      className="text-sm"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          form.handleSubmit(onSubmit);
                        }
                      }}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              );
            }}
          />
          <InputGroupAddon>
            <SearchIcon className="size-4" />
          </InputGroupAddon>
          {isOptionsOpen && (
            <InputGroupAddon align="inline-end">
              <Button
                type="button"
                size="icon-xs"
                variant="ghost"
                className="size-4 rounded hover:text-slate-500"
                onClick={() => setOptionsOpen(false)}
              >
                <XIcon className="size-4" />
              </Button>
            </InputGroupAddon>
          )}
        </InputGroup>
        <div
          ref={openRef}
          className={cn(
            "dark:bg-sidebar-dark absolute right-0 left-0 z-200 h-fit flex-col gap-5 rounded-b-lg border border-t-0 border-slate-900 bg-white p-5 px-5 text-xs shadow-2xl dark:border-slate-500",
            isOptionsOpen ? "animate-dropdown flex" : "hidden",
          )}
        >
          <CheckboxFormField
            reactHookForm={form}
            name="isStrict"
            label="Strict Search"
            formDescriptionClassName="text-xs"
            description="Requires keyword matches to be present in the search results"
          />
          <SelectFormField
            reactHookForm={form}
            name="stype"
            label="Search Result Type"
            ref={sTypeRef}
            options={QueryTypeSelectData}
          />
          {queryType === "annotation" && (
            <SelectFormField
              reactHookForm={form}
              name="atype"
              ref={aTypeRef}
              label="Annotation Type"
              options={(annotationTypes ?? []).map((type) => ({
                type: "item",
                value: type,
                node: capitalize(type, true),
              }))}
            />
          )}
          <Button type="submit" form="searchBarForm">
            Search
          </Button>
        </div>
      </form>
    </Form>
  );
};
