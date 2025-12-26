"use client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { XIcon } from "lucide-react";
import { parseAsString, useQueryState } from "nuqs";
import { parseAsBoolean } from "nuqs/server";
import { useTRPCQuery } from "@/lib/trpc/use-queries";
import { Spinner } from "@/components/Spinner";
import { Fragment, useMemo } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils/cn";

export const EntityEvents = () => {
  const [entityText, setEntityText] = useQueryState(
    "entity",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  const [entityType, setEntityType] = useQueryState(
    "entityType",
    parseAsString.withDefault("").withOptions({ clearOnDefault: true }),
  );
  const [showEvents, setShowEvents] = useQueryState(
    "showEvents",
    parseAsBoolean.withDefault(false).withOptions({ clearOnDefault: true }),
  );

  const { data, isPending } = useTRPCQuery((trpc) =>
    trpc.analytics.getEventsForEntity.queryOptions({
      entity: entityText,
      value: entityType,
    }),
  );

  const sections: { value: string; count: number }[] = useMemo(() => {
    if (data == null) {
      return [];
    }
    return data.map((s) => ({ value: s.value, count: s.count }));
  }, [data]);

  if (!entityType || !entityText || !showEvents) {
    return null;
  }

  const scrollTo = (id: string) => {
    const element = document.getElementById(id);
    if (element == null) return;
    element.scrollIntoView({
      behavior: "smooth",
    });
  };

  return (
    <Card className="absolute top-0 left-0 z-10 h-full w-full">
      <CardHeader>
        <CardTitle className="text-2xl">
          Events involving{" "}
          <span className="text-dodger-blue-500 font-black">
            {entityText} ({entityType})
          </span>
        </CardTitle>
        <CardDescription>
          Displays the events that the {entityText} has participated in.
        </CardDescription>
        <CardAction>
          <Button
            variant="ghost"
            onClick={() => {
              setEntityText("");
              setEntityType("");
              setShowEvents(false);
            }}
          >
            <XIcon />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex min-h-0 w-full flex-1 flex-col gap-4 p-3">
        {isPending || !data ? (
          <Spinner />
        ) : (
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-medium">Event Type</span>
            <Select onValueChange={(value) => scrollTo(value)}>
              <SelectTrigger className="w-[350px]">
                <SelectValue placeholder="Select an event type..." />
              </SelectTrigger>
              <SelectContent>
                {sections.map((section) => (
                  <SelectItem value={section.value} key={section.value}>
                    {section.value.replaceAll("_", " ").toUpperCase()} (
                    {section.count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="scrollable flex flex-1 flex-col gap-4 pr-2 pb-10">
          {data?.map((section) => (
            <div key={section.value} className="flex flex-col gap-1">
              <h1 className="pb-1" id={section.value}>
                {section.value.replaceAll("_", " ").toUpperCase()} (
                {section.count} Events)
              </h1>
              <div className="overflow-clip rounded-lg border">
                <table className="w-full">
                  <thead>
                    <tr className="bg-heading text-white">
                      <th className="p-0.5">Event Trigger</th>
                      <th className="p-0.5">A0</th>
                      <th className="p-0.5">A1</th>
                      <th className="p-0.5">Time</th>
                      <th className="p-0.5">Location</th>
                    </tr>
                  </thead>
                  <tbody>
                    {section.events.map((event, i) => (
                      <Fragment key={`${section.value}-${i}`}>
                        <tr
                          className={cn(
                            "bg-row text-sm",
                            i % 2 == 1 && "bg-alternate-row",
                          )}
                        >
                          <td className="p-1 text-center">{event.text}</td>
                          <td className="p-1 text-center whitespace-pre-wrap">
                            {event.A0?.map((a0, k) => (
                              <p key={k}>
                                {a0.toUpperCase() ===
                                entityText.toUpperCase() ? (
                                  <b className="text-blue-700 dark:text-blue-500">
                                    {a0}
                                  </b>
                                ) : (
                                  a0
                                )}
                              </p>
                            ))}
                          </td>
                          <td className="p-1 text-center">
                            {" "}
                            {event.A1?.map((a1, k) => (
                              <p key={k}>
                                {a1.toUpperCase() ===
                                entityText.toUpperCase() ? (
                                  <b className="text-blue-700 dark:text-blue-500">
                                    {a1}
                                  </b>
                                ) : (
                                  a1
                                )}
                              </p>
                            ))}
                          </td>
                          <td className="p-1 text-center">
                            {event.TIME == null ? (
                              "-"
                            ) : event.TIME.toUpperCase() ===
                              entityText.toUpperCase() ? (
                              <b className="text-blue-700 dark:text-blue-500">
                                {event.TIME}
                              </b>
                            ) : (
                              event.TIME
                            )}
                          </td>
                          <td className="p-1 text-center">
                            {event.LOC == null ? (
                              "-"
                            ) : event.LOC.toUpperCase() ===
                              entityText.toUpperCase() ? (
                              <b className="text-blue-700 dark:text-blue-500">
                                {event.LOC}
                              </b>
                            ) : (
                              event.LOC
                            )}
                          </td>
                        </tr>
                        <tr
                          className={cn(
                            "bg-row text-sm",
                            i % 2 == 1 && "bg-alternate-row",
                          )}
                        >
                          <td colSpan={5} className="text-muted-foreground p-2">
                            {event.sentence}
                          </td>
                        </tr>
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
