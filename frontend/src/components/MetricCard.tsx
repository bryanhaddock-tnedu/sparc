import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface MetricCardProps {
  label: string;
  value: string;
  tone?: "default" | "good" | "warn";
}

export function MetricCard({ label, value, tone = "default" }: MetricCardProps) {
  const valueClass = tone === "good" ? "text-primary" : tone === "warn" ? "text-destructive" : "text-foreground";

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
