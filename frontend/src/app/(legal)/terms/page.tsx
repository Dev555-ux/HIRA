import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { LegalSection } from "@/components/legal/legal-section";
import {
  ENTITY_NAME,
  GOVERNING_LAW,
  LEGAL_LAST_UPDATED,
  PRODUCT_NAME,
  SITE_URL,
  SUPPORT_EMAIL,
} from "@/lib/legal";

const TITLE = "Terms of Service";
const DESCRIPTION = `The terms that govern using ${PRODUCT_NAME}, provided by ${ENTITY_NAME}.`;

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/terms" },
};

export default function TermsOfServicePage() {
  return (
    <>
      <PageHeader title={TITLE} description={`Last updated ${LEGAL_LAST_UPDATED}`} />

      <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
        {PRODUCT_NAME} is provided by {ENTITY_NAME} (&quot;{ENTITY_NAME}&quot;, &quot;we&quot;,
        &quot;us&quot;) — currently an independent software project, not a registered company, LLP,
        or other formal legal entity. By creating a {PRODUCT_NAME} account or otherwise using the
        service, you agree to these terms.
      </p>

      <LegalSection title="The Service">
        <p>
          {PRODUCT_NAME} connects to a WhatsApp Business number a business already owns and
          answers that business&apos;s customers on WhatsApp, grounded in the knowledge the
          business has provided. It can book, reschedule, or cancel appointments through its own
          built-in scheduler, or through Google Calendar if a business connects it, and it tracks
          customers and leads. By default every AI-drafted reply or action goes through Assisted
          Mode — a human reviews it before anything is sent or executed — until a business
          chooses to enable Autonomous Mode for a specific action type.
        </p>
      </LegalSection>

      <LegalSection title="Acceptable Use">
        <p>You agree not to use {PRODUCT_NAME} to:</p>
        <ul>
          <li>
            Send unsolicited bulk messages or spam over WhatsApp, or otherwise violate Meta&apos;s
            WhatsApp Business Messaging Policy — {PRODUCT_NAME}&apos;s ability to message anyone
            depends on staying within Meta&apos;s own rules, for every business on the platform,
            not just yours.
          </li>
          <li>Impersonate another business or person, or connect a WhatsApp number you&apos;re not authorized to use.</li>
          <li>
            Upload knowledge-base content that&apos;s unlawful, deceptive, or infringes someone
            else&apos;s rights.
          </li>
          <li>Attempt to access another business&apos;s data or bypass the isolation between businesses on the platform.</li>
          <li>Use the service in a way that violates applicable law.</li>
        </ul>
      </LegalSection>

      <LegalSection title="Customer Responsibilities">
        <p>As a business using {PRODUCT_NAME}, you&apos;re responsible for:</p>
        <ul>
          <li>Connecting a WhatsApp Business number you&apos;re authorized to use.</li>
          <li>
            The accuracy of the knowledge base you provide — {PRODUCT_NAME} answers from what
            it&apos;s told, so an inaccurate or outdated entry produces an inaccurate answer.
          </li>
          <li>
            Reviewing how {PRODUCT_NAME} performs in Assisted Mode before enabling Autonomous
            Mode for any action.
          </li>
          <li>
            Your own compliance with applicable law in how you communicate with your customers,
            including any consent you need from them to be messaged.
          </li>
          <li>Keeping your account credentials secure.</li>
        </ul>
      </LegalSection>

      <LegalSection title="Service Availability">
        <p>
          {PRODUCT_NAME} is provided on an &quot;as available&quot; basis. As an early-stage,
          independently-run project, we don&apos;t currently offer a guaranteed uptime commitment
          or service-level agreement. {PRODUCT_NAME} also depends on third-party infrastructure —
          Meta&apos;s WhatsApp Cloud API, our hosting providers, and the AI model provider in
          use — whose availability we don&apos;t control; an outage on their end can affect
          {" "}{PRODUCT_NAME}. We&apos;ll make a reasonable effort to communicate any significant,
          known outage.
        </p>
      </LegalSection>

      <LegalSection title="Billing">
        <p>
          {PRODUCT_NAME} does not currently charge for access. If paid plans are introduced in the
          future, this section will be updated in advance, pricing will be clearly stated before
          any charge is made, and continued use of {PRODUCT_NAME} after that update takes effect
          will constitute acceptance of the then-current terms. No business will be billed
          retroactively for usage that occurred before a paid plan took effect.
        </p>
      </LegalSection>

      <LegalSection title="Intellectual Property">
        <p>
          {ENTITY_NAME} owns {PRODUCT_NAME} — the software, the platform, and everything that
          makes it work. You own your own data: your knowledge base content, your customer and
          lead records, and the content of your conversations. We don&apos;t claim ownership over
          anything a business or its customers put into {PRODUCT_NAME}.
        </p>
      </LegalSection>

      <LegalSection title="AI-Generated Content">
        <p>
          {PRODUCT_NAME}&apos;s replies and proposed actions are generated by an AI model grounded
          in the knowledge a business provides. You&apos;re responsible for reviewing that
          behavior — especially before enabling Autonomous Mode — and for the accuracy of the
          knowledge base it&apos;s grounded in. Subject to the limitation below, {ENTITY_NAME}{" "}
          isn&apos;t liable for losses arising from an AI-generated reply or action.
        </p>
      </LegalSection>

      <LegalSection title="Limitation of Liability">
        <p>
          To the maximum extent permitted by law, {PRODUCT_NAME} is provided without warranties of
          any kind, express or implied. {ENTITY_NAME} is not liable for indirect, incidental, or
          consequential damages arising from your use of {PRODUCT_NAME}. {ENTITY_NAME}&apos;s
          total liability for any claim relating to {PRODUCT_NAME} is limited to the amount, if
          any, you paid us in the twelve months before the claim arose.
        </p>
      </LegalSection>

      <LegalSection title="Account Termination">
        <p>
          You can stop using {PRODUCT_NAME} and request deletion of your account at any time —
          see our <a href="/data-deletion">Data Deletion Policy</a> for how that works. We may
          suspend or terminate an account that violates these terms, violates Meta&apos;s own
          platform policies (which would put the WhatsApp connection for that account, and
          potentially others, at risk), or violates applicable law.
        </p>
      </LegalSection>

      <LegalSection title="Changes to These Terms">
        <p>
          If we make a material change to these terms, we&apos;ll update the date at the top of
          this page and make a reasonable effort to let active businesses know.
        </p>
      </LegalSection>

      <LegalSection title="Governing Law">
        <p>
          These terms are governed by the laws of {GOVERNING_LAW}. {ENTITY_NAME} is not yet a
          formally incorporated entity, so a specific court or jurisdiction within India is not
          designated at this time — this section will be updated once {ENTITY_NAME} is formally
          established.
        </p>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          Questions about these terms: <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      </LegalSection>
    </>
  );
}
