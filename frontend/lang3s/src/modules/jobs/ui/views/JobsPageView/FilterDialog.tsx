"use client";
import { FilterState } from "@/components/data-table/data-table-types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { jobStatuses } from "@/db/schema";
import { cn } from "@/lib/utils";
import { ListFilterIcon, ListFilterPlusIcon } from "lucide-react";

export const FilterDialog = <T extends object>({
  setFilter,
  getFilter,
}: {
  setFilter: (state: FilterState<T>) => void;
  getFilter: (column: string) => FilterState<T> | undefined;
}) => {
  const hasFilter = getFilter("name") || getFilter("status");
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="listButton"
          className={cn(
            "transition-all",
            hasFilter &&
              "from-dodger-blue-300 bg-gradient-to-b to-sky-300 font-bold transition-all",
          )}
        >
          {hasFilter ? (
            <ListFilterIcon className="size-4" />
          ) : (
            <ListFilterPlusIcon className="size-4" />
          )}
          Filter
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Job Tracker Filters</DialogTitle>
          <DialogDescription className="sr-only">
            Sets filters for the job status table
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-6">
          <div className="space-y-1">
            <Label htmlFor="job_name">Job Name</Label>
            <Input
              id="job_name"
              value={(getFilter("name")?.value as string) ?? ""}
              onChange={(e) => {
                setFilter({
                  column: "name",
                  value: !!e.target.value ? e.target.value : null,
                });
              }}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="name">Status</Label>
            <Select
              value={(getFilter("status")?.value as string) ?? ""}
              onValueChange={(v) =>
                setFilter({
                  column: "status",
                  value: v === "None" ? null : v,
                })
              }
            >
              <SelectTrigger className="w-[300px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="None">-</SelectItem>
                {jobStatuses.map((status) => (
                  <SelectItem key={status} value={status}>
                    {status.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => {
              setFilter({ column: "name", value: undefined });
              setFilter({ column: "status", value: undefined });
            }}
          >
            Clear
          </Button>
          <DialogClose asChild>
            <Button>Ok</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
