import { FAQS } from "@/components/marketing/faq";
import { ENTITY_NAME, PRODUCT_NAME, SITE_URL } from "@/lib/legal";

// Organization/WebSite describe the business and the site itself — safe to
// state as fact regardless of product specifics. Deliberately no
// `legalName`/`sameAs`: Stoneveil isn't incorporated yet and has no official
// social profiles, and schema.org fields should never assert what isn't true.
// `logo` is app/icon.png (192px; Google needs at least 112px).
export function buildOrganizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: ENTITY_NAME,
    url: SITE_URL,
    logo: `${SITE_URL}/icon.png`,
  };
}

export function buildWebSiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: PRODUCT_NAME,
    url: SITE_URL,
  };
}

// No `offers`/price: pricing isn't public yet (see the FAQ's own "What does
// HIRA cost?" answer) — fabricating a price node here would be structured
// data Google could surface as fact.
export function buildSoftwareApplicationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: PRODUCT_NAME,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url: SITE_URL,
    description:
      "HIRA is the AI employee businesses hire to answer customers on WhatsApp, book appointments, and follow up on every lead.",
  };
}

export function buildFaqSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQS.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };
}
