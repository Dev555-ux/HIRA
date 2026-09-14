import type { Metadata } from "next";
import { MarketingPage } from "@/components/marketing/marketing-page";
import { pageMetadata } from "@/lib/seo";
import { buildFaqSchema, buildSoftwareApplicationSchema } from "@/lib/structured-data";

const TITLE = "HIRA — The AI Employee for WhatsApp-First Businesses";
const DESCRIPTION =
  "HIRA is the AI employee businesses hire to answer customers on WhatsApp, book appointments, and follow up on every lead — grounded in your own knowledge, supervised by you.";

export const metadata: Metadata = {
  ...pageMetadata({ title: TITLE, description: DESCRIPTION, path: "/" }),
  // Opts out of the root layout's "%s | HIRA" template — the brand already leads.
  title: { absolute: TITLE },
};

// Signed-in and mock-mode redirects to /dashboard happen in middleware.ts,
// which keeps this page free of request-time APIs and statically prerendered.
export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(buildSoftwareApplicationSchema()) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(buildFaqSchema()) }}
      />
      <MarketingPage />
    </>
  );
}
