import type { Metadata } from 'next';
import { Outfit } from 'next/font/google';
import './globals.css';

const outfit = Outfit({
  subsets: ['latin'],
  variable: '--font-outfit',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'SkillMap AI — Learn Smarter from YouTube',
    template: '%s | SkillMap AI',
  },
  description:
    'Convert YouTube playlists into structured learning roadmaps with progress tracking. Turn passive watching into active learning.',
  keywords: ['learning', 'youtube', 'roadmap', 'education', 'progress tracking'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={outfit.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
