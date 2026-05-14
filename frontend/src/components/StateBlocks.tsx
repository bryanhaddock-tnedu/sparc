import { Card, CardContent } from "./ui/card";

export function LoadingBlock() {
  return (
    <Card>
      <CardContent className="py-10 text-sm text-muted-foreground">Loading...</CardContent>
    </Card>
  );
}

export function ErrorBlock({ message }: { message: string }) {
  return (
    <Card className="border-destructive/40">
      <CardContent className="py-5 text-sm text-destructive">{message}</CardContent>
    </Card>
  );
}
