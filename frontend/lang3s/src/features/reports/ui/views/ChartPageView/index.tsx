"use client";

import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { DualAxisForm } from "@/features/reports/ui/views/ChartPageView/AxisForm";
import { ChartSchemaType } from "@/features/reports/schema";
import { useState } from "react";
import { ChartView } from "@/features/reports/ui/views/ChartPageView/Chart";

export const ChartViewPage = () => {
  const [axis, setAxis] = useState<ChartSchemaType | undefined>(undefined);
  return (
    <ScrollableBox.Container>
      <ScrollableBox.Header>
        <h1>Chart Page</h1>
        <p className="pageSubheading">Something...</p>
      </ScrollableBox.Header>
      {axis != null ? (
        <ChartView chart={axis} />
      ) : (
        <DualAxisForm setAxis={setAxis} />
      )}
    </ScrollableBox.Container>
  );
};
