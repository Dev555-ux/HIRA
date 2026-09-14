import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { LegalSection } from "@/components/legal/legal-section";
import { ENTITY_NAME, LEGAL_LAST_UPDATED, PRODUCT_NAME, SUPPORT_EMAIL } from "@/lib/legal";
import { pageMetadata } from "@/lib/seo";

const TITLE = "Data Deletion";
const DESCRIPTION = `How businesses and their customers request data deletion from ${PRODUCT_NAME}: what to email, how requests are verified, what gets deleted, and how long it takes.`;

export const metadata: Metadata = pageMetadata({ title: TITLE, description: DESCRIPTION, path: "/data-deletion" });

export default function DataDeletionPage() {
  return (
    <>
      <PageHeader title={TITLE} description={`Last updated ${LEGAL_LAST_UPDATED}`} />

      <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
        This page explains how a business using {PRODUCT_NAME}, or an individual who messaged a
        business through {PRODUCT_NAME}, can have their data deleted from{" "}
        {ENTITY_NAME}&apos;s systems. There is no self-service &quot;delete my account&quot;
        button in the product today — every deletion request is handled directly by our team, as
        described below.
      </p>

      <LegalSection title="How to Request Deletion">
        <p>
          Email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> and state that
          you&apos;re requesting deletion.
        </p>
        <ul>
          <li>
            If you&apos;re a business, send the request from the email address associated with
            your {PRODUCT_NAME} account.
          </li>
          <li>
            If you&apos;re an individual asking about your own WhatsApp conversation with a
            business that uses {PRODUCT_NAME}, include the WhatsApp number you messaged from and
            the name of the business you messaged, so we can locate the right data.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Verification">
        <p>
          Before acting on a request, we verify it&apos;s actually coming from the account owner
          or the individual concerned — this protects against someone else using a deletion
          request to remove data that isn&apos;t theirs.
        </p>
      </LegalSection>

      <LegalSection title="What Gets Deleted">
        <p>Once a request is verified, we delete everything tied to that business&apos;s account:</p>
        <ul>
          <li>The business account and its WhatsApp connection details stored in {PRODUCT_NAME}.</li>
          <li>Conversations and messages.</li>
          <li>Knowledge base entries.</li>
          <li>Appointments.</li>
          <li>Customer and lead records.</li>
          <li>Stored credentials (WhatsApp and, if connected, Google Calendar tokens).</li>
        </ul>
        <p>
          One important limit: deleting data from {PRODUCT_NAME} does not delete anything stored
          on Meta&apos;s own systems as the WhatsApp platform operator. If you also want your data
          removed from Meta&apos;s side, that&apos;s a separate request to Meta directly.
        </p>
      </LegalSection>

      <LegalSection title="Backups">
        <p>
          Deleted data may persist briefly in routine database backups until those backups are
          naturally cycled out as part of normal operations — it isn&apos;t individually purged
          from every backup the moment a request is processed.
        </p>
      </LegalSection>

      <LegalSection title="Timeline">
        <p>We aim to process verified deletion requests within 30 days.</p>
      </LegalSection>

      <LegalSection title="Confirmation">
        <p>
          Once a deletion is complete, we&apos;ll confirm by email to whoever made the request.
        </p>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      </LegalSection>
    </>
  );
}
