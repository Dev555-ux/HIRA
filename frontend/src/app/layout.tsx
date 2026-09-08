import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { buildOrganizationSchema, buildWebSiteSchema } from "@/lib/structured-data";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://stoneveil.in"),
  title: "HIRA Dashboard",
  description: "Manage your AI employee's conversations, bookings, and leads.",
  robots: {
    index: true,
    follow: true,
  },
};

// Matches globals.css's --background token for each color scheme, so the
// browser chrome (address bar on mobile) never clashes with the page itself.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "hsl(30 20% 99%)" },
    { media: "(prefers-color-scheme: dark)", color: "hsl(20 15% 5%)" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable}`}
    >
      <body className="min-h-screen antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(buildOrganizationSchema()) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(buildWebSiteSchema()) }}
        />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
