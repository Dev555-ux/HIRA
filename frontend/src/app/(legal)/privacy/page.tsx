import type { Metadata } from "next";
import { PageHeader } from "@/components/page-header";
import { LegalSection } from "@/components/legal/legal-section";
import { ENTITY_NAME, LEGAL_LAST_UPDATED, PRODUCT_NAME, SITE_URL, SUPPORT_EMAIL } from "@/lib/legal";

const TITLE = "Privacy Policy";
const DESCRIPTION = `How ${ENTITY_NAME} collects, uses, and protects data in ${PRODUCT_NAME}, including Google user data.`;

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
        {PRODUCT_NAME} to run their WhatsApp (and, where connected, Instagram) conversations, and{" "}
        <strong className="text-foreground">that business&apos;s own customers</strong>, whose
        messages {PRODUCT_NAME} processes on the business&apos;s behalf. If you&apos;re a customer
        messaging a business that happens to use {PRODUCT_NAME}, the business you&apos;re messaging
        is who you&apos;re actually talking to — see{" "}
        <a href="#whatsapp-data">WhatsApp and Instagram Data</a> below for how that works, and{" "}
        <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> if you have a question specific to
        how {PRODUCT_NAME} itself (not the business) handles something.
      </p>

      <LegalSection title="Introduction">
        <p>
          This policy explains what information {PRODUCT_NAME} collects, how it&apos;s used, who
          it&apos;s shared with, how it&apos;s protected, how long it&apos;s kept, and how it can be
          deleted — including, specifically, information accessed through Google APIs, since{" "}
          {PRODUCT_NAME} integrates with Google Calendar for businesses that choose to connect it.
        </p>
        <p>
          By using {PRODUCT_NAME}, either as a business or as someone messaging a business that uses
          {" "}{PRODUCT_NAME}, you&apos;re agreeing to how information is handled as described here.
        </p>
      </LegalSection>

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
            <strong className="text-foreground">Instagram messages</strong> — for businesses that
            connect an Instagram Business account, the content of direct messages sent to and from
            that account.
          </li>
          <li>
            <strong className="text-foreground">Business knowledge</strong> — FAQs, pricing,
            hours, policies, or anything else a business types directly into {PRODUCT_NAME}, or
            imports from a public webpage it provides, so {PRODUCT_NAME} can answer its customers
            accurately.
          </li>
          <li>
            <strong className="text-foreground">Calendar and appointment data</strong> —
            bookings made through {PRODUCT_NAME}&apos;s own built-in scheduler, and, only if a
            business chooses to connect it, data accessed via Google Calendar — see{" "}
            <a href="#google-calendar-integration">Google Calendar Integration</a> below.
          </li>
          <li>
            <strong className="text-foreground">Customer and lead records</strong> — names,
            contact details, and sales-pipeline status a business tracks about its own customers,
            including notes the business writes.
          </li>
          <li>
            <strong className="text-foreground">Platform credentials</strong> — the WhatsApp
            Business Account ID, Instagram Business account details, and access tokens{" "}
            {PRODUCT_NAME} needs to send and receive messages on a business&apos;s behalf. Stored
            encrypted, never in plain text.
          </li>
          <li>
            <strong className="text-foreground">Technical data</strong> — standard server logs
            and error reports, used to keep the service running and to fix bugs. We do not log
            message content or full request bodies in these logs — see{" "}
            <a href="#security">Security</a>.
          </li>
        </ul>
        <p>
          We do not currently process payments or collect payment information — {PRODUCT_NAME}{" "}
          does not charge for access today. If that changes, this policy will be updated before
          payment collection begins.
        </p>
      </LegalSection>

      <LegalSection title="Account Information">
        <p>
          Account information (name, email, business profile) is provided directly by the
          business at signup and managed through our authentication provider, Clerk. We use it to
          identify who&apos;s using {PRODUCT_NAME}, scope all of a business&apos;s data to that
          business, and to contact the business about its account.
        </p>
      </LegalSection>

      <LegalSection title="Google User Data">
        <p>
          Google user data enters {PRODUCT_NAME} only through one integration:{" "}
          <strong className="text-foreground">Google Calendar</strong>, and only for a business
          that explicitly chooses to connect it — it is never required to use {PRODUCT_NAME}.
        </p>
        <p>
          <strong className="text-foreground">
            {PRODUCT_NAME}&apos;s use and transfer of information received from Google APIs will
            adhere to the Google API Services User Data Policy, including the Limited Use
            requirements.
          </strong>
        </p>
        <p>Concretely, that means:</p>
        <ul>
          <li>
            Google Calendar data is used <strong className="text-foreground">only</strong> to
            power the appointment-scheduling features described below — never for advertising,
            never sold or shared with data brokers or third parties for their own purposes, and
            never used to train any AI model.
          </li>
          <li>
            Access is limited to what&apos;s needed for scheduling; we do not read the titles,
            descriptions, attendees, or content of a business&apos;s other, pre-existing calendar
            events.
          </li>
          <li>
            Human access to Google Calendar data is limited to what&apos;s necessary for support
            and debugging, and is logged.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Google Calendar Integration">
        <div id="google-calendar-integration" className="scroll-mt-24 space-y-4">
          <p>
            When a business connects Google Calendar, {PRODUCT_NAME} requests the{" "}
            <code>https://www.googleapis.com/auth/calendar</code> scope. We ask for this specific
            scope — rather than a read-only one — because {PRODUCT_NAME} needs to both check
            availability and create the appointments it books:
          </p>
          <ul>
            <li>
              <strong className="text-foreground">Free/busy time</strong> on the connected
              calendar, to determine when the business is actually available before offering a
              time slot to a customer.
            </li>
            <li>
              <strong className="text-foreground">
                The ability to create, update, and cancel calendar events
              </strong>
              , to place a confirmed appointment on the business&apos;s calendar when{" "}
              {PRODUCT_NAME} books one, and to update or remove it if the appointment is
              rescheduled or cancelled.
            </li>
          </ul>
          <p>
            We do <strong className="text-foreground">not</strong> read the content of events
            already on a business&apos;s calendar — only free/busy status, and only the events{" "}
            {PRODUCT_NAME} itself creates.
          </p>
          <ul>
            <li>
              <strong className="text-foreground">How it&apos;s protected:</strong> the Google
              refresh token is encrypted at rest before it&apos;s stored, never held in plain
              text.
            </li>
            <li>
              <strong className="text-foreground">How long it&apos;s retained:</strong> for as
              long as the connection stays active — i.e., until the business disconnects Google
              Calendar or closes its {PRODUCT_NAME} account.
            </li>
            <li>
              <strong className="text-foreground">When it&apos;s deleted:</strong> disconnecting
              (available any time from the business&apos;s settings) deletes our stored copy of
              the credential immediately. Disconnecting does not, on its own, revoke{" "}
              {PRODUCT_NAME}&apos;s access grant on Google&apos;s side — you can additionally
              revoke it at any time from your{" "}
              <a
                href="https://myaccount.google.com/permissions"
                target="_blank"
                rel="noopener noreferrer"
              >
                Google Account&apos;s third-party access page
              </a>
              , and we recommend doing so if you want to fully sever the connection.
            </li>
            <li>
              <strong className="text-foreground">Sharing:</strong> Google Calendar data is never
              sold, never used for advertising, and never shared with any third party except as
              needed to operate the calendar feature itself (i.e., with Google, as the calendar
              provider).
            </li>
          </ul>
        </div>
      </LegalSection>

      <LegalSection title="AI Processing">
        <p>
          When {PRODUCT_NAME} answers a customer message, it sends the relevant conversation, the
          matching knowledge-base content, and relevant business context (such as the
          customer&apos;s name, pipeline stage, and any upcoming appointment time) to a large
          language model provider to generate a reply. Depending on how a given deployment is
          configured, that provider is either{" "}
          <strong className="text-foreground">Anthropic (Claude)</strong> or{" "}
          <strong className="text-foreground">Groq</strong> — never both for the same message —
          and that provider processes the data under its own standard commercial API terms.{" "}
          {ENTITY_NAME} does not operate its own foundation model and does not use business data
          to train one.
        </p>
        <p>
          For long-running conversations, {PRODUCT_NAME} also periodically asks the same AI
          provider to summarize older messages into a shorter running summary, so future replies
          stay accurate without re-sending the full history every time. That summary is stored and
          reused the same way the conversation itself is.
        </p>
        <p>
          By default, {PRODUCT_NAME} runs in{" "}
          <strong className="text-foreground">Assisted Mode</strong>: every AI-drafted reply or
          proposed action (a booking, a lead update) is reviewed by the business before it&apos;s
          sent or executed. A business can choose to turn on{" "}
          <strong className="text-foreground">Autonomous Mode</strong> for specific actions, which
          removes that review step for those actions only — this is always a choice the business
          makes, never a default.
        </p>
        <p>
          Turning a business&apos;s knowledge base into something {PRODUCT_NAME} can search
          happens locally — the text is converted into vector embeddings by a model that runs on
          {" "}{ENTITY_NAME}&apos;s own infrastructure, not sent to a third-party embeddings API.
        </p>
      </LegalSection>

      <LegalSection title="WhatsApp and Instagram Data">
        <div id="whatsapp-data" className="scroll-mt-24 space-y-4">
          <p>
            {PRODUCT_NAME} connects to a WhatsApp Business number, and optionally an Instagram
            Business account, through Meta&apos;s APIs. Using either channel at all means messages
            inherently pass through Meta&apos;s own platform — Meta processes that data as the
            platform operator, under its own terms, separately from and in addition to{" "}
            {ENTITY_NAME}&apos;s own processing described in this policy. We don&apos;t control
            how Meta itself handles data; see Meta&apos;s own WhatsApp Business Platform and
            Instagram terms and privacy policy for that.
          </p>
          <p>
            Every inbound message {PRODUCT_NAME} receives from Meta is authenticated with a
            cryptographic signature check before it&apos;s processed, so we can be confident a
            message actually came from Meta and wasn&apos;t forged.
          </p>
        </div>
      </LegalSection>

      <LegalSection title="Uploaded Documents">
        <p>
          {PRODUCT_NAME} does not currently support uploading documents or files of any kind.
          Business knowledge is added only by typing it directly into {PRODUCT_NAME} or by
          importing text from a public webpage the business provides. If document upload is added
          in the future, this policy will be updated before that feature launches.
        </p>
      </LegalSection>

      <LegalSection title="Conversation History">
        <p>
          Message content, sender/recipient phone numbers or handles, timestamps, and delivery
          status are stored for as long as the relevant business account is active, so the
          business can see its own conversation history and so {PRODUCT_NAME} can use recent
          context to generate accurate replies. There is currently no fixed automatic expiry on
          conversation data — it is retained until the business deletes the relevant records or
          requests account deletion — see{" "}
          <a href="#account-deletion">Account &amp; Data Deletion</a>.
        </p>
      </LegalSection>

      <LegalSection title="Cookies">
        <p>
          {PRODUCT_NAME}&apos;s dashboard uses one cookie: an authentication/session cookie set
          by our sign-in provider, Clerk, to keep a business owner signed in. That&apos;s the
          only cookie in use today — no advertising cookies, no analytics cookies, no tracking
          pixels.
        </p>
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

      <LegalSection title="Sharing of Information">
        <p>We share information only as needed to operate {PRODUCT_NAME}:</p>
        <ul>
          <li>
            With the AI provider (Anthropic or Groq) to generate a reply, as described in{" "}
            <a href="#ai-processing">AI Processing</a>.
          </li>
          <li>
            With Google, only for a business that connects Google Calendar, as described in{" "}
            <a href="#google-calendar-integration">Google Calendar Integration</a>.
          </li>
          <li>
            With Meta, as the operator of the WhatsApp Business Platform and Instagram, since
            using either channel inherently routes messages through Meta&apos;s own
            infrastructure — see{" "}
            <a href="#whatsapp-data">WhatsApp and Instagram Data</a>.
          </li>
          <li>With our hosting and infrastructure providers, solely to run the service.</li>
          <li>
            If required by law, or to protect the rights, safety, or property of {ENTITY_NAME},
            our users, or the public.
          </li>
        </ul>
        <p>
          We do not sell information, and we do not share it with third parties for their own
          advertising or marketing purposes.
        </p>
      </LegalSection>

      <LegalSection title="Google API Limited Use Statement">
        <p>
          <strong className="text-foreground">
            {PRODUCT_NAME}&apos;s use and transfer of information received from Google APIs will
            adhere to the Google API Services User Data Policy, including the Limited Use
            requirements.
          </strong>{" "}
          See <a href="#google-calendar-integration">Google Calendar Integration</a> above for the
          specifics of what&apos;s accessed, why, and how it&apos;s protected.
        </p>
      </LegalSection>

      <LegalSection title="Third-Party Services">
        <p>The services below each process only what they need to do their specific job:</p>
        <ul>
          <li>
            <strong className="text-foreground">Meta Platforms, Inc.</strong> — the WhatsApp
            Business Platform and, where connected, Instagram.
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
            <strong className="text-foreground">Sentry</strong> — error monitoring, configured to
            exclude message content and sensitive headers.
          </li>
          <li>
            Our hosting and infrastructure providers, which run the application, database, and
            this website.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Security">
        <div id="security" className="scroll-mt-24 space-y-4">
          <ul>
            <li>Every business&apos;s data is isolated from every other business&apos;s data.</li>
            <li>
              Stored credentials — WhatsApp and Instagram access tokens, Google Calendar refresh
              tokens — are encrypted at rest, not stored as plain text.
            </li>
            <li>All traffic to {PRODUCT_NAME} is served over HTTPS.</li>
            <li>
              Every inbound request, including Meta&apos;s own webhooks, is cryptographically
              verified before being acted on.
            </li>
            <li>
              Our error-monitoring tooling is configured to exclude message content and sensitive
              request headers from what it captures.
            </li>
          </ul>
          <p>
            No system is perfectly secure. If something changes that materially affects how your
            data is protected, we&apos;ll update this page and, where appropriate, contact
            affected businesses directly.
          </p>
        </div>
      </LegalSection>

      <LegalSection title="Data Retention">
        <p>
          We keep data for as long as a business&apos;s account is active. There is no fixed
          automatic expiry on conversation, customer, or knowledge-base data today — it&apos;s
          retained until a business deletes specific records itself, disconnects an integration,
          or requests account deletion. Routine database backups are kept for 14 days and then
          automatically cycled out. If a business asks us to delete its data, we follow the
          process described in our <a href="/data-deletion">Data Deletion Policy</a>.
        </p>
      </LegalSection>

      <LegalSection title="Account & Data Deletion">
        <div id="account-deletion" className="scroll-mt-24 space-y-4">
          <p>
            There is no self-service &quot;delete my account&quot; button in {PRODUCT_NAME} today
            — every deletion request is handled directly by our team. Full details, including how
            to request deletion, how we verify a request, what gets deleted, and our timeline, are
            in our <a href="/data-deletion">Data Deletion Policy</a>. In short:
          </p>
          <ul>
            <li>
              A business can request deletion of everything tied to its account at any time by
              emailing <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
            </li>
            <li>
              Once verified, we delete the business&apos;s conversations, messages, knowledge
              base, appointments, customer and lead records, and stored platform credentials
              (WhatsApp, Instagram, and Google Calendar tokens).
            </li>
            <li>
              Deleting data from {PRODUCT_NAME} does not delete anything stored on Meta&apos;s own
              systems as the WhatsApp or Instagram platform operator — that&apos;s a separate
              request to Meta directly.
            </li>
            <li>
              Deleted data may persist briefly in routine backups (up to 14 days) until those
              backups are naturally cycled out.
            </li>
            <li>
              We aim to process verified deletion requests within 30 days, and confirm by email
              once complete.
            </li>
          </ul>
          <p>
            Individual businesses can also delete specific customers, leads, or knowledge-base
            entries themselves at any time from within the product, without needing to contact us.
          </p>
        </div>
      </LegalSection>

      <LegalSection title="Your Rights">
        <p>
          A business can access, correct, or request deletion of its data at any time by
          contacting <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>. If you&apos;re an
          individual who messaged a business on WhatsApp or Instagram, start with that business
          directly — they hold the relationship with you — and reach us at the same address for
          anything specific to {PRODUCT_NAME}&apos;s own handling of your data.
        </p>
        <p>
          Until a formal Grievance Officer is appointed, all privacy and data requests should be
          sent to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
        </p>
      </LegalSection>

      <LegalSection title="Children's Privacy">
        <p>
          {PRODUCT_NAME} is intended for use by businesses and their adult representatives, not by
          children. We do not knowingly collect information directly from children under 18. If
          you believe a child has provided us information directly (as opposed to being a
          customer&apos;s contact messaging a business), contact us at{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> and we&apos;ll delete it.
        </p>
      </LegalSection>

      <LegalSection title="International Transfers">
        <p>
          {ENTITY_NAME} is based in India, and data may be processed there. Some of the providers
          described in this policy — including Anthropic, Groq, Google, Clerk, and our hosting
          providers — may process data in other countries, including the United States. Where
          that happens, we rely on those providers&apos; own safeguards and standard commercial
          terms, and take reasonable steps consistent with applicable law to protect information
          transferred internationally.
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
