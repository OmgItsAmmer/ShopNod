import { cookies } from 'next/headers';
import { getRequestConfig } from 'next-intl/server';
import en from '../messages/en.json';
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale, mergeMessages } from './config';

export default getRequestConfig(async () => {
  const jar = await cookies();
  const cookie = jar.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookie) ? cookie : DEFAULT_LOCALE;
  const messages = locale === 'en' ? en : mergeMessages(en, (await import(`../messages/${locale}.json`)).default);
  return { locale, messages, timeZone: 'UTC' };
});
