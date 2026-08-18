<!-- EDITOR'S NOTE (not part of the published policy):
This document is Deliverable 2 — a new, standalone Privacy Policy replacing (not patching)
frontend/src/app/(legal)/privacy/page.tsx. It is written for direct adaptation into that page's
existing PageHeader/LegalSection component structure, using the constants already defined in
frontend/src/lib/legal.ts (ENTITY_NAME, PRODUCT_NAME, SUPPORT_EMAIL, GOVERNING_LAW, SITE_URL).

BEFORE PUBLISHING: frontend/src/lib/legal.ts:5-8 carries a founder-dated TODO stating Stoneveil is
not yet incorporated, and that ENTITY_NAME/GOVERNING_LAW/the Grievance Officer name are placeholders
pending incorporation. This document uses those constants as-is, for consistency with every other
page on the site — but publishing a privacy policy naming a legal entity that doesn't yet exist is
itself a compliance risk worth resolving first, or at minimum a conscious founder decision to accept.
See PRIVACY_POLICY_AUDIT.md Unresolved Question #1 and PRIVACY_POLICY_IMPLEMENTATION_TASKS.md.

Every factual claim below is backed by PRIVACY_POLICY_AUDIT.md. No retention period, deletion
behavior, or integration is stated here that isn't verified in that audit.
-->

# Privacy Policy

**Last updated:** August 18, 2026

HIRA is built by Stoneveil ("**Stoneveil**," "**we**," "**us**"). This policy covers two different
groups of people: **businesses** that sign up for HIRA to run their WhatsApp (and, where connected,
Instagram) conversations, and **that business's own customers**, whose messages HIRA processes on
the business's behalf.

If you're a customer messaging a business that happens to use HIRA, the business you're messaging is
who you're actually talking to — see [WhatsApp Data](#whatsapp-and-instagram-data) below for how that
works. Reach us at [support@stoneveil.in](mailto:support@stoneveil.in) for anything specific to how
HIRA itself, rather than the business, handles your data.

---

## 1. Introduction

This policy explains what information HIRA collects, how it's used, who it's shared with, how it's
protected, how long it's kept, and how it can be deleted — including, specifically, information
accessed through Google APIs, since HIRA integrates with Google Calendar for businesses that choose
to connect it.

By using HIRA, either as a business or as someone messaging a business that uses HIRA, you're
agreeing to how information is handled as described here.

## 2. Information We Collect

We collect the following, only as needed to run the product:

- **Account information** — name, email, and business details (business name, industry, country,
  timezone) provided at signup.
- **WhatsApp messages** — the content of messages sent to and from the business's connected WhatsApp
  number, the phone numbers involved, timestamps, and delivery status.
- **Instagram messages** — for businesses that connect an Instagram Business account, the content of
  direct messages sent to and from that account.
- **Business knowledge** — FAQs, pricing, hours, policies, or anything else a business types directly
  into HIRA, or imports from a public webpage it provides, so HIRA can answer its customers
  accurately.
- **Calendar and appointment data** — bookings made through HIRA's own built-in scheduler, and, only
  if a business chooses to connect it, data accessed via Google Calendar (see [Google Calendar
  Integration](#5-google-calendar-integration) below).
- **Customer and lead records** — names, contact details, and sales-pipeline status a business tracks
  about its own customers, including notes the business writes.
- **Platform credentials** — the WhatsApp Business Account ID, Instagram Business account details,
  and access tokens HIRA needs to send and receive messages on a business's behalf. Stored encrypted,
  never in plain text.
- **Technical data** — standard server logs and error reports, used to keep the service running and
  to fix bugs. We do not log message content or full request bodies in these logs (see
  [Security](#14-security)).

We do not currently process payments or collect payment information — HIRA does not charge for access
today. If that changes, this policy will be updated before payment collection begins.

## 3. Account Information

Account information (name, email, business profile) is provided directly by the business at signup
and managed through our authentication provider, Clerk. We use it to identify who's using HIRA, scope
all of a business's data to that business, and to contact the business about its account.

## 4. Google User Data

Google user data enters HIRA only through one integration: **Google Calendar**, and only for a
business that explicitly chooses to connect it — it is never required to use HIRA.

**HIRA's use and transfer of information received from Google APIs will adhere to the [Google API
Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.**

Concretely, that means:

- Google Calendar data is used **only** to power the appointment-scheduling features described below
  — never for advertising, never sold or shared with data brokers or third parties for their own
  purposes, and never used to train any AI model.
- Access is limited to what's needed for scheduling; we do not read the titles, descriptions,
  attendees, or content of a business's other, pre-existing calendar events.
- Human access to Google Calendar data is limited to what's necessary for support and debugging, and
  is logged.

## 5. Google Calendar Integration

When a business connects Google Calendar, HIRA requests the `https://www.googleapis.com/auth/calendar`
scope. We ask for this specific scope — rather than a read-only one — because HIRA needs to both check
availability and create the appointments it books:

| What we access | Why |
|---|---|
| Free/busy time on the connected calendar | To determine when the business is actually available before offering a time slot to a customer |
| The ability to create, update, and cancel calendar events | To place a confirmed appointment on the business's calendar when HIRA books one, and to update or remove it if the appointment is rescheduled or cancelled |

We do **not** read the content of events already on a business's calendar — only free/busy status, and
only the events HIRA itself creates.

- **How it's protected:** the Google refresh token is encrypted at rest before it's stored, never held
  in plain text.
- **How long it's retained:** for as long as the connection stays active — i.e., until the business
  disconnects Google Calendar or closes its HIRA account.
- **When it's deleted:** disconnecting (available any time from the business's settings) deletes our
  stored copy of the credential immediately. Disconnecting does not, on its own, revoke HIRA's access
  grant on Google's side — you can additionally revoke it at any time from your [Google Account's
  third-party access page](https://myaccount.google.com/permissions), and we recommend doing so if you
  want to fully sever the connection.
- **Sharing:** Google Calendar data is never sold, never used for advertising, and never shared with
  any third party except as needed to operate the calendar feature itself (i.e., with Google, as the
  calendar provider).

## 6. AI Processing

When HIRA answers a customer message, it sends the relevant conversation, the matching
knowledge-base content, and relevant business context (such as the customer's name, pipeline stage,
and any upcoming appointment time) to a large language model provider to generate a reply. Depending
on how a given deployment is configured, that provider is either **Anthropic (Claude)** or **Groq** —
never both for the same message — and that provider processes the data under its own standard
commercial API terms. Stoneveil does not operate its own foundation model and does not use business
data to train one.

For long-running conversations, HIRA also periodically asks the same AI provider to summarize older
messages into a shorter running summary, so future replies stay accurate without re-sending the full
history every time. That summary is stored and reused the same way the conversation itself is.

By default, HIRA runs in **Assisted Mode**: every AI-drafted reply or proposed action (a booking, a
lead update) is reviewed by the business before it's sent or executed. A business can choose to turn
on **Autonomous Mode** for specific actions, which removes that review step for those actions only —
this is always a choice the business makes, never a default.

Turning a business's knowledge base into something HIRA can search happens **locally** — the text is
converted into vector embeddings by a model that runs on our own infrastructure, not sent to a
third-party embeddings API.

## 7. Uploaded Documents

HIRA does not currently support uploading documents or files of any kind. Business knowledge is added
only by typing it directly into HIRA or by importing text from a public webpage the business provides.
If document upload is added in the future, this policy will be updated before that feature launches.

## 8. Conversation History

Message content, sender/recipient phone numbers or handles, timestamps, and delivery status are
stored for as long as the relevant business account is active, so the business can see its own
conversation history and so HIRA can use recent context to generate accurate replies. There is
currently no fixed automatic expiry on conversation data — it is retained until the business deletes
the relevant records or requests account deletion (see [Account & Data Deletion](#16-account--data-deletion)).

## 9. Cookies

HIRA's dashboard uses one cookie: an authentication/session cookie set by our sign-in provider,
Clerk, to keep a business owner signed in. That's the only cookie in use today — no advertising
cookies, no analytics cookies, no tracking pixels.

## 10. How We Use Information

Information is used to operate HIRA itself: answering customer messages, retrieving the right
knowledge to ground a reply, managing bookings, and tracking leads for the business that owns that
data. We also use technical logs to debug and keep the service reliable.

We do not sell any of this information, and we do not use it for advertising.

## 11. Sharing of Information

We share information only as needed to operate HIRA:

- With the AI provider (Anthropic or Groq) to generate a reply, as described in [AI
  Processing](#6-ai-processing).
- With Google, only for a business that connects Google Calendar, as described in [Google Calendar
  Integration](#5-google-calendar-integration).
- With Meta, as the operator of the WhatsApp Business Platform and Instagram, since using either
  channel inherently routes messages through Meta's own infrastructure (see [WhatsApp and Instagram
  Data](#whatsapp-and-instagram-data)).
- With our hosting and infrastructure providers, solely to run the service.
- If required by law, or to protect the rights, safety, or property of Stoneveil, our users, or the
  public.

We do not sell information, and we do not share it with third parties for their own advertising or
marketing purposes.

## 12. Google API Limited Use Statement

**HIRA's use and transfer of information received from Google APIs will adhere to the Google API
Services User Data Policy, including the Limited Use requirements.** See [Google User
Data](#4-google-user-data) and [Google Calendar Integration](#5-google-calendar-integration) above for
the specifics of what's accessed, why, and how it's protected.

## 13. Third-Party Services

The services below each process only what they need to do their specific job:

- **Meta Platforms, Inc.** — the WhatsApp Business Platform and, where connected, Instagram.
- **Anthropic and/or Groq** — AI reply generation, whichever is configured for a given deployment.
- **Google** — Calendar sync, only for businesses that choose to connect it.
- **Clerk** — dashboard authentication.
- **Sentry** — error monitoring, configured to exclude message content and sensitive headers.
- Our hosting and infrastructure providers, which run the application, database, and this website.

## 14. Security

- Every business's data is isolated from every other business's data.
- Stored credentials — WhatsApp and Instagram access tokens, Google Calendar refresh tokens — are
  encrypted at rest, not stored as plain text.
- All traffic to HIRA is served over HTTPS.
- Every inbound request, including Meta's own webhooks, is cryptographically verified before being
  acted on.
- Our error-monitoring tooling is configured to exclude message content and sensitive request headers
  from what it captures.

No system is perfectly secure. If something changes that materially affects how your data is
protected, we'll update this page and, where appropriate, contact affected businesses directly.

## 15. Data Retention

We keep data for as long as a business's account is active. There is no fixed automatic expiry on
conversation, customer, or knowledge-base data today — it's retained until a business deletes specific
records itself, disconnects an integration, or requests account deletion. Routine database backups are
kept for 14 days and then automatically cycled out. If a business asks us to delete its data, we
follow the process described in our [Data Deletion Policy](/data-deletion).

## 16. Account & Data Deletion

There is no self-service "delete my account" button in HIRA today — every deletion request is handled
directly by our team. Full details, including how to request deletion, how we verify a request, what
gets deleted, and our timeline, are in our [Data Deletion Policy](/data-deletion). In short:

- A business can request deletion of everything tied to its account at any time by emailing
  [support@stoneveil.in](mailto:support@stoneveil.in).
- Once verified, we delete the business's conversations, messages, knowledge base, appointments,
  customer and lead records, and stored platform credentials (WhatsApp, Instagram, and Google
  Calendar tokens).
- Deleting data from HIRA does not delete anything stored on Meta's own systems as the WhatsApp or
  Instagram platform operator — that's a separate request to Meta directly.
- Deleted data may persist briefly in routine backups (up to 14 days) until those backups are
  naturally cycled out.
- We aim to process verified deletion requests within 30 days, and confirm by email once complete.

Individual businesses can also delete specific customers, leads, or knowledge-base entries themselves
at any time from within the product, without needing to contact us.

## 17. Your Rights

A business can access, correct, or request deletion of its data at any time by contacting
[support@stoneveil.in](mailto:support@stoneveil.in). If you're an individual who messaged a business
on WhatsApp or Instagram, start with that business directly — they hold the relationship with you —
and reach us at the same address for anything specific to HIRA's own handling of your data.

Until a formal Grievance Officer is appointed, all privacy and data requests should be sent to
[support@stoneveil.in](mailto:support@stoneveil.in).

## 18. Children's Privacy

HIRA is intended for use by businesses and their adult representatives, not by children. We do not
knowingly collect information directly from children under 18. If you believe a child has provided us
information directly (as opposed to being a customer's contact messaging a business), contact us at
[support@stoneveil.in](mailto:support@stoneveil.in) and we'll delete it.

## 19. International Transfers

Stoneveil is based in India, and data may be processed there. Some of the providers described in this
policy — including Anthropic, Groq, Google, Clerk, and our hosting providers — may process data in
other countries, including the United States. Where that happens, we rely on those providers' own
safeguards and standard commercial terms, and take reasonable steps consistent with applicable law to
protect information transferred internationally.

## 20. Changes to this Policy

If we make a material change to this policy, we'll update the date at the top of this page and make a
reasonable effort to let active businesses know.

## 21. Contact Information

Questions about this policy, or a request relating to your data:
[support@stoneveil.in](mailto:support@stoneveil.in).

---

<a id="whatsapp-and-instagram-data"></a>
## WhatsApp and Instagram Data

HIRA connects to a WhatsApp Business number, and optionally an Instagram Business account, through
Meta's APIs. Using either channel at all means messages inherently pass through Meta's own platform —
Meta processes that data as the platform operator, under its own terms, separately from and in
addition to Stoneveil's own processing described in this policy. We don't control how Meta itself
handles data; see Meta's own WhatsApp Business Platform and Instagram terms and privacy policy for
that.

Every inbound message HIRA receives from Meta is authenticated with a cryptographic signature check
before it's processed, so we can be confident a message actually came from Meta and wasn't forged.
