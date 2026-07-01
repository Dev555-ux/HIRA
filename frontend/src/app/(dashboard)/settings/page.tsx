"use client";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuthContext } from "@/lib/auth-context";

export default function SettingsPage() {
  const { mocked } = useAuthContext();

  return (
    <>
      <PageHeader title="Settings" description="Configure your business and integrations." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Business information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Business name" placeholder="Acme Clinic" />
            <Field label="Timezone" placeholder="UTC" />
            <Button size="sm" disabled title="Settings API coming soon">
              Save
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Mode" value={<Badge variant="secondary">Assisted</Badge>} />
            <Row label="Model" value="llama-3.3-70b-versatile" />
            <Row label="Embeddings" value="local bge-small (384d)" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Integration status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Clerk auth" value={<Badge variant={mocked ? "warning" : "success"}>{mocked ? "Mock (dev)" : "Connected"}</Badge>} />
            <Row label="Groq" value={<Badge variant="success">Live</Badge>} />
            <Row label="WhatsApp" value={<Badge variant="secondary">Paused</Badge>} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">WhatsApp configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="Phone number ID" placeholder="Awaiting dedicated number" disabled />
            <Field label="Access token" placeholder="•••••••• (paused)" disabled />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function Field({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium">{label}</span>
      <Input {...props} />
    </label>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}
