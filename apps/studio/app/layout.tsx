import './globals.css';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { Providers } from './providers';

export const metadata: Metadata = {
  title: 'Chainos Studio',
  description: 'The data factory — build · verify · publish',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <header
            style={{
              borderBottom: '1px solid var(--border)',
              padding: '14px 24px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <a href="/" style={{ fontWeight: 700, fontSize: 18, color: 'var(--text)' }}>
              ⛓ Chainos <span className="dim">Studio</span>
            </a>
            <span className="dim" style={{ fontSize: 12 }}>
              Admin · data factory — Staging → Publish → Production
            </span>
          </header>
          <main style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
