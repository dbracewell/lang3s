import { useCallback } from "react";

interface ExportOptions {
  filename?: string;
  backgroundColor?: string;
  scale?: number;
  fontFamily?: string;
}

export const useSvgExport = () => {
  const exportSvg = useCallback(
    async (svgElement: SVGSVGElement | null, options: ExportOptions = {}) => {
      if (!svgElement) return;

      const {
        filename = "chart-export.png",
        backgroundColor = "#ffffff",
        scale = 3,
        fontFamily = "Arial, sans-serif",
      } = options;

      // 1. Capture dimensions
      const bounds = svgElement.getBoundingClientRect();
      const { width, height } = bounds;

      // 2. Clone and Inline Styles
      const clonedSvg = svgElement.cloneNode(true) as SVGSVGElement;
      clonedSvg.setAttribute("width", width.toString());
      clonedSvg.setAttribute("height", height.toString());
      clonedSvg.setAttribute("viewBox", `0 0 ${width} ${height}`);

      const svgElements = clonedSvg.querySelectorAll("*");
      const originalElements = svgElement.querySelectorAll("*");

      svgElements.forEach((el, i) => {
        const style = window.getComputedStyle(originalElements[i]);
        const htmlEl = el as HTMLElement;

        // Map computed CSS to inline attributes
        htmlEl.style.fill = style.fill;
        htmlEl.style.stroke = style.stroke;
        htmlEl.style.opacity = style.opacity;
        htmlEl.style.fontSize = style.fontSize;
        htmlEl.style.fontWeight = style.fontWeight;
        htmlEl.style.fontFamily = fontFamily; // Force standard font

        if (style.textAnchor) htmlEl.style.textAnchor = style.textAnchor;
        if (style.display === "none") htmlEl.style.display = "none";
      });

      // 3. Prepare Canvas
      const canvas = document.createElement("canvas");
      canvas.width = width * scale;
      canvas.height = height * scale;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      // 4. Fill background to prevent banding
      ctx.fillStyle = backgroundColor;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // 5. Render SVG to Canvas
      const svgData = new XMLSerializer().serializeToString(clonedSvg);
      const svgBlob = new Blob([svgData], {
        type: "image/svg+xml;charset=utf-8",
      });
      const url = URL.createObjectURL(svgBlob);
      const img = new Image();

      img.onload = () => {
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
        ctx.drawImage(img, 0, 0);

        canvas.toBlob((blob) => {
          if (!blob) return;
          const downloadUrl = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = downloadUrl;
          link.download = filename;
          link.click();

          // Cleanup
          URL.revokeObjectURL(url);
          URL.revokeObjectURL(downloadUrl);
        }, "image/png");
      };

      img.src = url;
    },
    [],
  );

  return { exportSvg };
};
