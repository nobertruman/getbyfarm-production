// Fonts are self-hosted from npm packages: no third-party requests at runtime or build time.
import "@fontsource/space-grotesk/500.css";
import "@fontsource/space-grotesk/700.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/caveat/600.css";
import "./globals.css";

export const metadata = {
  title: { default: "GetbyFarm: smarter sourcing for hospitality", template: "%s · GetbyFarm" },
  description:
    "Compare verified wholesale suppliers, buy with M-Pesa, and keep every branch stocked. Procurement for Kenyan restaurants, hotels and caterers.",
};
export const viewport = { themeColor: "#0C850D", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="font-body antialiased">{children}</body>
    </html>
  );
}
