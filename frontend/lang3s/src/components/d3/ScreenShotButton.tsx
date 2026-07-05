import { useD3Context } from "@/components/d3/D3ContextType";
import { useSvgExport } from "@/hooks/useSvgExport";
import { useTheme } from "next-themes";
import { Hint } from "@/components/hint";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { VariantProps } from "class-variance-authority";
import { FileImageIcon } from "lucide-react";

export const ScreenShotButton = ({
  fileNamePrefix,
  className,
  variant = "listButton",
  size = "icon",
}: {
  fileNamePrefix: string;
  className?: string;
  variant?: VariantProps<typeof buttonVariants>["variant"];
  size?: VariantProps<typeof buttonVariants>["size"];
}) => {
  const { exportSvg } = useSvgExport();
  const { getRef } = useD3Context();
  const { theme } = useTheme();
  const saveSvg = async () => {
    const svg = getRef("svg").current;
    if (svg == null) return;
    const lightMode = "#fafafa";
    const darkMode = "#171717";
    await exportSvg(svg, {
      filename: `${fileNamePrefix}-${Date.now()}.png`,
      backgroundColor: theme === "dark" ? darkMode : lightMode,
      scale: 3,
    });
  };
  return (
    <Hint hint={"Export view as png"} asChild>
      <Button
        onClick={saveSvg}
        variant={variant}
        size={size}
        className={cn("absolute", className)}
      >
        <FileImageIcon />
      </Button>
    </Hint>
  );
};
