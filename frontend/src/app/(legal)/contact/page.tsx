import { Mail } from "lucide-react";
import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ENTITY_NAME, PRODUCT_NAME, SUPPORT_EMAIL } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

const TITLE = "Contact";
const DESCRIPTION = `Contact the ${ENTITY_NAME} team behind ${PRODUCT_NAME} at ${SUPPORT_EMAIL} — one address for product questions, support, privacy and data requests, and business inquiries.`;

export const metadata: Metadata = pageMetadata({ title: TITLE, description: DESCRIPTION, path: "/contact" });

export default function ContactPage() {
  return (
    <>
      <PageHeader title={TITLE} />

      <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
        We&apos;re a small, independent team building {PRODUCT_NAME} — one email reaches us for
        anything: product questions, support, privacy or data requests, and business inquiries.
        Expect a reply from a real person, not a ticket number.
      </p>

      <Card className="mt-8">
        <CardContent className="flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Email us</p>
            <p className="text-sm text-muted-foreground">{SUPPORT_EMAIL}</p>
          </div>
          <Button asChild>
            <a href={`mailto:${SUPPORT_EMAIL}`}>
              <Mail /> Email {SUPPORT_EMAIL}
            </a>
          </Button>
        </CardContent>
      </Card>
    </>
  );
}
