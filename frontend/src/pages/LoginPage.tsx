import { LockKeyhole, LogIn } from "lucide-react";
import { FormEvent, useState } from "react";

import tdoeLogo from "../assets/tdoe-logo.png";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { useAuth } from "../lib/auth";
import { appConfig } from "../lib/config";

export function LoginPage() {
  const { login, status } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  function signInWithEntra() {
    window.location.assign(`${appConfig.apiBaseUrl}/api/auth/entra/login`);
  }

  return (
    <div className="min-h-screen bg-background">
      <div
        aria-hidden="true"
        className="h-1"
        style={{
          background:
            "linear-gradient(90deg, var(--spark-red) 0 33.33%, var(--spark-navy) 33.33% 66.66%, var(--spark-gray) 66.66% 100%)",
        }}
      />
      <main className="mx-auto flex min-h-[calc(100vh-4px)] max-w-md flex-col justify-center px-4 py-10">
        <div className="mb-6 flex items-center justify-center gap-3 text-primary">
          <img src={tdoeLogo} alt="TDOE logo" className="h-10 w-auto" />
          <div>
            <div className="text-xl font-semibold leading-none">SPARC</div>
            <div className="mt-1 text-sm text-muted-foreground">Staff Planning and Resource Control</div>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <LockKeyhole className="h-5 w-5" />
              Sign in
            </CardTitle>
          </CardHeader>
          <CardContent>
            {status?.entra_enabled ? (
              <div className="mb-5 space-y-4">
                <Button className="w-full" type="button" onClick={signInWithEntra}>
                  <LogIn className="h-4 w-4" />
                  Sign in with TDOE SSO
                </Button>
                <div className="flex items-center gap-3 text-xs uppercase text-muted-foreground">
                  <div className="h-px flex-1 bg-border" />
                  or
                  <div className="h-px flex-1 bg-border" />
                </div>
              </div>
            ) : null}

            <form className="space-y-4" onSubmit={(event) => void submit(event)}>
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="username">
                  Email or username
                </label>
                <Input
                  id="username"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="password">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>

              {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}

              <Button className="w-full" type="submit" disabled={submitting}>
                <LockKeyhole className="h-4 w-4" />
                {submitting ? "Signing in" : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
