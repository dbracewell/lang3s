"use client";
import { CheckboxFormField } from "@/components/form-controls/checkbox-form-field";
import { InputFormField } from "@/components/form-controls/input-form-field";
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
import { cn } from "@/lib/utils";
import { QueryTypes } from "@/modules/search/types";
import {
  ParsedSearchParams,
  parseUrlSearchParams,
  SearchParamSchema,
  toSearchParams,
} from "@/modules/search/utils/parse-params";
import { useTRPCQuery } from "@/trpc/use-queries";
import { zodResolver } from "@hookform/resolvers/zod";
import { SearchIcon, XIcon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

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
  const searchParams = useSearchParams();
  const [isOptionsOpen, setOptionsOpen] = useState(false);
  const router = useRouter();
  const { data: annotationTypes } = useTRPCQuery((trpc) =>
    trpc.analytics.getAnnotationTypes.queryOptions(),
  );
  const form = useForm<ParsedSearchParams>({
    resolver: zodResolver(SearchParamSchema),
    defaultValues: {
      ...parseUrlSearchParams(searchParams),
    },
  });

  const queryType = form.watch("queryType");
  const isSemantic = form.watch("semanticSearch");
  const aid = form.watch("annotationId");

  const onSubmit = (values: ParsedSearchParams) => {
    router.push(`/search?${toSearchParams(values)}`);
    setOptionsOpen(false);
  };

  useEffect(() => {
    const v = parseUrlSearchParams(searchParams);
    form.reset();
    Object.entries(v).forEach(([k, v]) =>
      form.setValue(
        k as
          | "query"
          | "annotationId"
          | "annotationType"
          | "minSimilarity"
          | "page"
          | "semanticSearch"
          | "lang",
        v,
      ),
    );
    form.setValue("query", v.query ?? undefined);
  }, [searchParams, form]);

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        id="searchBarForm"
        className="group relative z-100"
        onFocus={() => setOptionsOpen(true)}
      >
        <InputGroup
          className={cn(
            "w-full rounded-full bg-slate-200",
            isOptionsOpen &&
              "rounded-none rounded-t-lg border border-b-0 border-slate-900 bg-slate-50",
          )}
        >
          <FormField
            control={form.control}
            name="query"
            render={({ field }) => {
              return (
                <FormItem className="flex-1">
                  <FormControl>
                    <InputGroupInput
                      placeholder="Search..."
                      value={field.value ?? ""}
                      onChange={(e) => {
                        field.onChange(e);
                        form.setValue("annotationId", undefined);
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
            name="semanticSearch"
            label="Semantic Search"
            formDescriptionClassName="text-xs"
            description="Searches for related concepts instead of keyword matches"
            onCheckedChange={(e) => {
              if (!e) {
                form.setValue("minSimilarity", 0);
              } else {
                form.setValue("minSimilarity", 0.4);
              }
            }}
          />
          <SelectFormField
            reactHookForm={form}
            name="queryType"
            label="Search Result Type"
            options={QueryTypeSelectData}
          />
          {queryType === "annotation" && (
            <SelectFormField
              reactHookForm={form}
              name="annotationType"
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
          {isSemantic && aid == null && (
            <SelectFormField
              reactHookForm={form}
              name="lang"
              label="Language"
              defaultValue="en"
              options={[
                ["en", "English"],
                ["es", "Spanish"],
                ["ja", "Japanese"],
                ["zh", "Chinese"],
              ].map(([code, name]) => ({
                type: "item",
                value: code,
                node: capitalize(name, true),
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
