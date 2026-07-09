import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FileBarChartIcon } from "lucide-react";
import React from "react";
import { formatNumber } from "@/lib/utils/formatters";

export const CorpusStats = ({
  summary,
}: {
  summary: {
    documents: number;
    sentences: number;
    annotations: number;
  };
}) => {
  if (!summary) {
    return (
      <Card className="w-full">
        <CardContent className="flex h-full w-full flex-col items-center justify-center">
          <FileBarChartIcon className="text-muted-foreground size-20" />
          <span className="text-muted-foreground">
            No summary generated yet.
          </span>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-xl">Corpus Statistics</CardTitle>
        <CardDescription>General corpus statistics</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col">
        <table>
          <tbody>
            <tr>
              <td className="w-40 p-1 font-bold">Total Documents</td>
              <td className="p-1">{formatNumber(summary.documents)}</td>
              <td colSpan={2}></td>
            </tr>
            <tr>
              <td className="w-40 p-1 font-bold">Total Sentences</td>
              <td className="p-1">{formatNumber(summary.sentences)}</td>
              <td className="w-60 p-1 font-bold">Sentences / Document</td>
              <td className="p-1">
                {formatNumber(summary.sentences / summary.documents)}
              </td>
            </tr>
            <tr>
              <td className="w-40 p-1 font-bold">Total Annotations</td>
              <td className="p-1">{formatNumber(summary.annotations)}</td>
              <td className="w-60 p-1 font-bold">Annotations / Document</td>
              <td className="p-1">
                {formatNumber(summary.annotations / summary.documents)}
              </td>
            </tr>
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
};
