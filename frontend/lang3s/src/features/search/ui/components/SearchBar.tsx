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
import { capitalize } from "@/lib/formatters";
import { formatURL } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import {
  Lang3sSearchParams,
  ParsedSearchParams,
  QueryTypes,
  SearchParamSchema,
} from "@/features/search/params";
import { useTRPCQuery } from "@/trpc/use-queries";
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

  const closeSearchOptions = (doingSearch: boolean) => {
    setOptionsOpen(false);
    if (!doingSearch) {
      setFormValues();
    }
  };

  useClickOutside([searchBarRef, sTypeRef, aTypeRef], () =>
    closeSearchOptions(false),
  );

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
  const isSemantic = form.watch("semantic");

  const onSubmit = (values: ParsedSearchParams) => {
    router.push(formatURL("/search", values));
    closeSearchOptions(true);
  };

  const setFormValues = useCallback(() => {
    form.setValue("q", searchParams.q ?? undefined);
    form.setValue("atype", searchParams.atype);
    form.setValue("stype", searchParams.stype);
    form.setValue("aid", searchParams.aid);
    form.setValue("minSimilarity", searchParams.minSimilarity);
    form.setValue("page", searchParams.page);
    form.setValue("semantic", searchParams.semantic);
  }, [form, searchParams]);

  useEffect(() => {
    setFormValues();
  }, [setFormValues]);

  return (
    <Form {...form}>
      <form
        ref={searchBarRef}
        onSubmit={form.handleSubmit(onSubmit)}
        id="searchBarForm"
        className="group relative z-100"
        onFocus={() => setOptionsOpen(true)}
      >
        <InputGroup
          className={cn(
            "w-full rounded-full bg-slate-200 hover:shadow-md",
            isOptionsOpen &&
              "rounded-none rounded-t-lg border border-b-0 border-slate-900 bg-slate-50",
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
            <SearchIcon />
          </InputGroupAddon>
          {isOptionsOpen && (
            <InputGroupAddon align="inline-end">
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                className="size-5 rounded p-1! hover:text-slate-500"
                onClick={() => setOptionsOpen(false)}
              >
                <XIcon className="size-4" />
              </Button>
            </InputGroupAddon>
          )}
        </InputGroup>
        <div
          className={cn(
            "absolute right-0 left-0 z-200 h-fit flex-col gap-5 rounded-b-lg border border-t-0 border-slate-900 bg-white p-5 px-5 text-xs shadow-2xl",
            isOptionsOpen ? "animate-dropdown flex" : "hidden",
          )}
        >
          <CheckboxFormField
            reactHookForm={form}
            name="semantic"
            label="Semantic Search"
            formDescriptionClassName="text-xs"
            description="Searches for related concepts instead of keyword matches"
            onCheckedChange={(e) => {
              if (!e) {
                form.setValue("minSimilarity", 0);
              } else {
                form.setValue("minSimilarity", 0.6);
              }
            }}
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
          {isSemantic && (
            <NumberInputFormField
              reactHookForm={form}
              name="minSimilarity"
              label="Min Similarity."
              min={0.1}
              max={1}
              step={0.05}
              className="bg-white"
              formDescriptionClassName="text-xs"
              description="A higher similarity will more strictly match, but will return fewer results."
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
