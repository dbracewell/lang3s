import { SearchIcon } from "lucide-react";

export const SearchSpinner = () => {
  return (
    <div className="flex min-h-full flex-1 flex-col items-center justify-center">
      <SearchIcon className="text-dodger-blue-500 size-20 animate-pulse" />
      <span className="text-lg font-bold">Searching...</span>
    </div>
  );
};
