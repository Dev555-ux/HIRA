import { auth } from "@clerk/nextjs/server";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { MarketingPage } from "@/components/marketing/marketing-page";
import { authEnabled } from "@/lib/config";

const SITE_URL = "https://hira-tau.vercel.app";
const DESCRIPTION =
  "HIRA is an AI receptionist for WhatsApp-first businesses. It answers customer questions from your own knowledge base, books appointments into your calendar, and escalates to a human when it isn't sure.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "HIRA — The AI Receptionist for WhatsApp-First Businesses",
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    title: "HIRA — The AI Receptionist for WhatsApp-First Businesses",
    description: DESCRIPTION,
    url: "/",
    siteName: "HIRA",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "HIRA — The AI Receptionist for WhatsApp-First Businesses",
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
  return <MarketingPage />;
}
