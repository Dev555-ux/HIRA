import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { LegalSection } from "@/components/legal/legal-section";
import { ENTITY_NAME, PRODUCT_NAME, SUPPORT_EMAIL } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

const TITLE = "Company Information";
const DESCRIPTION = `${ENTITY_NAME} is the independent software project building ${PRODUCT_NAME}, an AI employee that answers customers on WhatsApp, books appointments, and tracks leads.`;

export const metadata: Metadata = pageMetadata({ title: TITLE, description: DESCRIPTION, path: "/company" });

export default function CompanyPage() {
  return (
    <>
      <PageHeader title={TITLE} />

      <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
        {ENTITY_NAME} is the independent software project building {PRODUCT_NAME}, founded by two
        individuals. {ENTITY_NAME} is not yet a registered company, LLP, or other formal legal
        entity — this page will be updated with full registration details once that changes.
      </p>

      <LegalSection title="What we build">
        <p>
          {PRODUCT_NAME} is an AI employee for WhatsApp-first businesses: it answers customers on
          a business&apos;s own WhatsApp Business number, grounded in that business&apos;s own
          knowledge, books appointments, and tracks leads — reviewed by the business itself before
          anything is sent or executed, until the business chooses otherwise.
        </p>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> — the one address for anything:
          product questions, support, or business inquiries.
        </p>
      </LegalSection>

      <LegalSection title="Legal">
        <p>
          See our <a href="/privacy">Privacy Policy</a>,{" "}
          <a href="/terms">Terms of Service</a>, and{" "}
          <a href="/data-deletion">Data Deletion Policy</a>.
        </p>
      </LegalSection>
    </>
  );
}
