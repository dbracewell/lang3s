import { ScrollableBox } from "@/components/scrolling/Scrollbox";
import { DualAxisForm } from "@/features/reports/ui/views/ChartPageView/AxisForm";
import { ChartView } from "@/features/reports/ui/views/ChartPageView/ChartView";

export const ChartViewPage = () => {
  return (
    <ScrollableBox.Container className="relative m-1">
      <ScrollableBox.Header>
        <h1>Chart Wizard</h1>
        <p className="pageSubheading">Select what you want to plot.</p>
      </ScrollableBox.Header>
      {/*<ChartView />*/}
      <DualAxisForm />
    </ScrollableBox.Container>
  );
};
