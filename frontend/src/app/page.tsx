import { auth } from "@clerk/nextjs/server";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { MarketingPage } from "@/components/marketing/marketing-page";
import { authEnabled } from "@/lib/config";
import { SITE_URL } from "@/lib/legal";
import { buildFaqSchema, buildSoftwareApplicationSchema } from "@/lib/structured-data";

const TITLE = "HIRA — The AI Employee for WhatsApp-First Businesses";
const DESCRIPTION =
  "HIRA is the AI employee businesses hire to answer customers on WhatsApp, book appointments, and follow up on every lead — grounded in your own knowledge, supervised by you.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  robots: {
  index: true,
  follow: true,
},
  alternates: { canonical: "/" },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: "/",
    siteName: "HIRA",
    type: "website",
  },
  twitter: {
    // opengraph-image.tsx supplies the image for both — Next.js reuses a
    // page's Open Graph image for Twitter when no twitter-image is set.
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
};

export default async function Home() {
  // Mock/dev mode has no real public/private distinction — go straight to
  // the dashboard, unchanged from before this page had marketing content.
  if (!authEnabled) {
    redirect("/dashboard");
  }
  const { userId } = await auth();
  if (userId) {
    redirect("/dashboard");
  }
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
