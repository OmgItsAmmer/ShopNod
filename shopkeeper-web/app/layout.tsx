import type { Metadata, Viewport } from 'next';
import { Geist } from 'next/font/google';
import { NextIntlClientProvider } from 'next-intl';
import { getLocale, getMessages, getTranslations } from 'next-intl/server';
import { Providers } from '@/components/providers';
import { directionOf } from '@/i18n/config';
import './globals.css';

const geist = Geist({ subsets: ['latin'], variable: '--font-geist', display: 'swap' });

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('meta');
  return {
    title: { default: t('title'), template: '%s · ShopNod' },
    description: t('description'),
    applicationName: 'ShopNod',
    manifest: '/manifest.webmanifest',
    icons: { icon: '/icon-192.png', apple: '/apple-touch-icon.png' },
    appleWebApp: { capable: true, title: 'ShopNod', statusBarStyle: 'default' },
  };
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#4B68FF' },
    { media: '(prefers-color-scheme: dark)', color: '#121212' },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  const t = await getTranslations('common');
  return (
    <html lang={locale} dir={directionOf(locale)} suppressHydrationWarning>
      <body className={`${geist.variable} min-h-dvh bg-background text-foreground antialiased`}>
        <a href="#main" className="skip-link">
          {t('skipToContent')}
        </a>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
