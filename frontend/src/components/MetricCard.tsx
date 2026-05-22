import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface MetricCardProps {
  label: string;
  value: string;
  tone?: "default" | "good" | "warn";
  density?: "default" | "compact";
}

export function MetricCard({ label, value, tone = "default", density = "default" }: MetricCardProps) {
  const valueClass = tone === "good" ? "text-primary" : tone === "warn" ? "text-destructive" : "text-foreground";
  if (density === "compact") {
    return (
      <Card className="min-h-[78px]">
        <CardContent className="grid h-full min-h-[78px] grid-rows-[1rem_1fr] gap-1 p-3">
          <div className="truncate text-[11px] font-semibold uppercase text-muted-foreground" title={label}>
            {label}
          </div>
          <div className={`numeric-cell flex items-center justify-center text-center text-2xl font-semibold leading-none ${valueClass}`}>
            {value}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="min-h-[118px]">
      <CardHeader className="p-4 pb-0">
        <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[72px] items-center justify-center p-4 pt-2">
        <div className={`numeric-cell text-center text-2xl font-semibold leading-none sm:text-3xl ${valueClass}`}>{value}</div>
      </CardContent>
    </Card>
  );
}
