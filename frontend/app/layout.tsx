import type { Metadata } from "next";
import { AppShell } from "../components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "SignalSafe | Harmful content related to sexual violence in armed conflicts",
  description: "Submit and review links containing harmful content related to sexual violence in armed conflicts.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
