import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { LegalSection } from "@/components/legal/legal-section";
import { ENTITY_NAME, LEGAL_LAST_UPDATED, PRODUCT_NAME, SITE_URL, SUPPORT_EMAIL } from "@/lib/legal";

const TITLE = "Privacy Policy";
const DESCRIPTION = `How ${ENTITY_NAME} collects, uses, and protects data in ${PRODUCT_NAME}.`;

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPolicyPage() {
  return (
    <>
      <PageHeader title={TITLE} description={`Last updated ${LEGAL_LAST_UPDATED}`} />

      <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
        {PRODUCT_NAME} is built by {ENTITY_NAME}, and this policy covers two different groups of
        people: <strong className="text-foreground">businesses</strong> that sign up for{" "}
        {PRODUCT_NAME} to run their WhatsApp conversations, and{" "}
        <strong className="text-foreground">that business&apos;s own customers</strong>, whose
        WhatsApp messages {PRODUCT_NAME} processes on the business&apos;s behalf. If
        you&apos;re a customer messaging a business that happens to use {PRODUCT_NAME}, the
        business you&apos;re messaging is who you&apos;re actually talking to — see{" "}
        <a href="#whatsapp-data">WhatsApp Data</a> below for how that works, and{" "}
        <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> if you have a question specific to
        how {PRODUCT_NAME} itself (not the business) handles something.
      </p>

      <LegalSection title="Information We Collect">
        <p>We collect the following, only as needed to run the product:</p>
        <ul>
          <li>
            <strong className="text-foreground">Account information</strong> — name, email, and
            business details (business name, industry, country, timezone) provided at signup.
          </li>
          <li>
            <strong className="text-foreground">WhatsApp messages</strong> — the content of
            messages sent to and from the business&apos;s connected WhatsApp number, the phone
            numbers involved, timestamps, and delivery status.
          </li>
          <li>
            <strong className="text-foreground">Business knowledge</strong> — FAQs, pricing,
            hours, policies, or anything else a business enters or imports (for example, from its
            own website) so {PRODUCT_NAME} can answer its customers accurately.
          </li>
          <li>
            <strong className="text-foreground">Calendar and appointment data</strong> —
            bookings made through {PRODUCT_NAME}&apos;s own built-in scheduler, and, only if a
            business chooses to connect it, calendar event data via Google Calendar, limited to
            calendar access.
          </li>
          <li>
            <strong className="text-foreground">Customer and lead records</strong> — names,
            contact details, and pipeline status a business tracks about its own customers.
          </li>
          <li>
            <strong className="text-foreground">WhatsApp Business Account credentials</strong> —
            the phone number ID, business account ID, and access token {PRODUCT_NAME} needs to
            send and receive messages on a business&apos;s behalf. Stored encrypted, never in
            plain text.
          </li>
          <li>
            <strong className="text-foreground">Technical data</strong> — standard server logs
            and error reports, used to keep the service running and to fix bugs.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="How We Use Information">
        <p>
          Information is used to operate {PRODUCT_NAME} itself: answering customer messages,
          retrieving the right knowledge to ground a reply, managing bookings, and tracking leads
          for the business that owns that data. We also use technical logs to debug and keep the
          service reliable.
        </p>
        <p>We do not sell any of this information, and we do not use it for advertising.</p>
      </LegalSection>

      <LegalSection title="AI Processing">
        <p>
          When {PRODUCT_NAME} answers a message, the relevant conversation and the matching
          knowledge-base content are sent to a large language model provider to generate a reply.
          Depending on how a given deployment is configured, that provider is either{" "}
          <strong className="text-foreground">Anthropic (Claude)</strong> or{" "}
          <strong className="text-foreground">Groq</strong> — never both for the same message —
          and that provider processes the data under its own standard commercial API terms.{" "}
          {ENTITY_NAME} does not operate its own foundation model and does not use business data
          to train one.
        </p>
        <p>
          By default, {PRODUCT_NAME} runs in <strong className="text-foreground">Assisted
          Mode</strong>: every AI-drafted reply or proposed action (a booking, a lead update) is
          reviewed by the business before it&apos;s sent or executed. A business can choose to turn
          on <strong className="text-foreground">Autonomous Mode</strong> for specific actions,
          which removes that review step for those actions only — this is always a choice the
          business makes, never a default.
        </p>
        <p>
          Turning a business&apos;s knowledge base into something {PRODUCT_NAME} can search
          happens locally — the text is converted into vector embeddings by a model that runs on{" "}
          {ENTITY_NAME}&apos;s own infrastructure, not sent to a third-party embeddings API.
        </p>
      </LegalSection>

      <LegalSection title="WhatsApp Data">
        <div id="whatsapp-data" className="scroll-mt-24 space-y-4">
          <p>
            {PRODUCT_NAME} connects to a WhatsApp Business number through Meta&apos;s WhatsApp
            Cloud API. Using WhatsApp at all means messages inherently pass through Meta&apos;s
            own platform — Meta processes that data as the platform operator, under its own
            terms, separately from and in addition to {ENTITY_NAME}&apos;s own processing
            described in this policy. We don&apos;t control how Meta itself handles data; see
            Meta&apos;s own WhatsApp Business Platform terms and privacy policy for that.
          </p>
          <p>
            Every inbound message {PRODUCT_NAME} receives from Meta is authenticated with an HMAC
            signature check before it&apos;s processed, so we can be confident a message actually
            came from Meta and wasn&apos;t forged.
          </p>
        </div>
      </LegalSection>

      <LegalSection title="Cookies">
        <p>
          {PRODUCT_NAME}&apos;s dashboard uses one cookie: an authentication/session cookie set
          by our sign-in provider, Clerk, to keep a business owner signed in. That&apos;s the
          only cookie in use today — no advertising or analytics cookies.
        </p>
      </LegalSection>

      <LegalSection title="Third-Party Services">
        <p>The services below each process only what they need to do their specific job:</p>
        <ul>
          <li>
            <strong className="text-foreground">Meta Platforms, Inc.</strong> — the WhatsApp
            Business Platform itself.
          </li>
          <li>
            <strong className="text-foreground">Anthropic and/or Groq</strong> — AI reply
            generation, whichever is configured for a given deployment.
          </li>
          <li>
            <strong className="text-foreground">Google</strong> — Calendar sync, only for
            businesses that choose to connect it.
          </li>
          <li>
            <strong className="text-foreground">Clerk</strong> — dashboard authentication.
          </li>
          <li>
            <strong className="text-foreground">Railway</strong> — hosts the application and
            database.
          </li>
          <li>
            <strong className="text-foreground">Vercel</strong> — hosts this website and
            dashboard frontend.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Security">
        <ul>
          <li>Every business&apos;s data is isolated from every other business&apos;s data.</li>
          <li>
            Stored credentials — WhatsApp access tokens, Google Calendar refresh tokens — are
            encrypted at rest, not stored as plain text.
          </li>
          <li>All traffic to {PRODUCT_NAME} is served over HTTPS.</li>
          <li>
            Every inbound request, including Meta&apos;s own webhooks, is validated before
            being acted on.
          </li>
        </ul>
        <p>
          No system is perfectly secure. If something changes that materially affects how your
          data is protected, we&apos;ll update this page and, where appropriate, contact affected
          businesses directly.
        </p>
      </LegalSection>

      <LegalSection title="Data Retention">
        <p>
          We keep data for as long as a business&apos;s account is active. If a business asks us
          to delete its data, we follow the process described in our{" "}
          <a href="/data-deletion">Data Deletion Policy</a>.
        </p>
      </LegalSection>

      <LegalSection title="Your Rights">
        <p>
          A business can access, correct, or request deletion of its data at any time by
          contacting <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>. If you&apos;re an
          individual who messaged a business on WhatsApp, start with that business directly —
          they hold the relationship with you — and reach us at the same address for anything
          specific to {PRODUCT_NAME}&apos;s own handling of your data.
        </p>
        <p>
          Until a formal Grievance Officer is appointed, all privacy and data requests should be
          sent to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      </LegalSection>

      <LegalSection title="Changes to This Policy">
        <p>
          If we make a material change to this policy, we&apos;ll update the date at the top of
          this page and make a reasonable effort to let active businesses know.
        </p>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          Questions about this policy, or a request relating to your data:{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      </LegalSection>
    </>
  );
}
