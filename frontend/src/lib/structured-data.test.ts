import { describe, expect, it } from "vitest";
import { FAQS } from "@/components/marketing/faq";
import {
  buildFaqSchema,
  buildOrganizationSchema,
  buildSoftwareApplicationSchema,
  buildWebSiteSchema,
} from "@/lib/structured-data";

describe("structured data", () => {
  it("produces JSON-serializable schema.org objects", () => {
    for (const schema of [
      buildOrganizationSchema(),
      buildWebSiteSchema(),
      buildSoftwareApplicationSchema(),
      buildFaqSchema(),
    ]) {
      expect(() => JSON.parse(JSON.stringify(schema))).not.toThrow();
      expect(schema["@context"]).toBe("https://schema.org");
    }
  });

  it("maps every FAQ into the FAQPage schema, in order", () => {
    const schema = buildFaqSchema();

    expect(schema.mainEntity).toHaveLength(FAQS.length);
    expect(schema.mainEntity[0]).toEqual({
      "@type": "Question",
      name: FAQS[0].question,
      acceptedAnswer: { "@type": "Answer", text: FAQS[0].answer },
    });
  });

  it("never states a price — pricing isn't public yet", () => {
    expect(buildSoftwareApplicationSchema()).not.toHaveProperty("offers");
  });
});
