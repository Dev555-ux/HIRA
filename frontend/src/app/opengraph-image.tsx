import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Generated at request time from brand tokens — no design asset to keep in
// sync. Matches globals.css's dark --background/--foreground pairing.
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 24,
          background: "#120f0e",
          color: "#faf8f6",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: 120, fontWeight: 900, letterSpacing: -4 }}>HIRA</div>
        <div style={{ fontSize: 32, opacity: 0.8 }}>
          The AI Employee for WhatsApp-First Businesses
        </div>
      </div>
    ),
    size,
  );
}
