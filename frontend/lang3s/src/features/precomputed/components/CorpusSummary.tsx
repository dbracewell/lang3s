import { Card, CardContent } from "@/components/ui/card";
import { NotebookIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import Link from "next/link";

export const CorpusSummary = ({ summary }: { summary?: string }) => {
  if (!summary) {
    return (
      <Card className="w-full lg:w-1/2">
        <CardContent className="flex h-full w-full flex-col items-center justify-center">
          <NotebookIcon className="text-muted-foreground size-20" />
          <span className="text-muted-foreground">
            No summary generated yet.
          </span>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="h-[99%] w-full lg:w-1/2">
      <CardContent className="scrollable prose dark:prose-invert flex min-h-0 min-w-full flex-1 flex-col">
        <ReactMarkdown
          rehypePlugins={[rehypeRaw]}
          remarkPlugins={[remarkGfm, remarkBreaks]}
          components={{
            a: ({ node, ...props }) => (
              <Link href={props.href!} className="link" {...props} />
            ),
            pre: ({ node, ...props }) => (
              <pre className="m-0! flex min-h-100 flex-col overflow-hidden bg-transparent! p-0!">
                <pre className="scrollable" {...props} />
              </pre>
            ),
          }}
        >
          {summary}
        </ReactMarkdown>
      </CardContent>
    </Card>
  );
};
