import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ZeroTrust ID Governance | みらい建設工業',
  description: 'EntraID × HENGEONE × AD 統合アイデンティティ管理ポータル',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja" className="dark">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
