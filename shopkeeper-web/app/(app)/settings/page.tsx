'use client';

import { useTranslations } from 'next-intl';
import { DemoSection, HoursSection, McpSection, NotificationsSection, ProfileSection } from '@/components/settings-sections';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function SettingsPage() {
  const t = useTranslations('settings');
  return (
    <div className="grid gap-5">
      <h1 className="text-3xl font-extrabold">{t('title')}</h1>
      <Tabs defaultValue="profile">
        <TabsList aria-label={t('title')}>
          <TabsTrigger value="profile">{t('tabs.profile')}</TabsTrigger>
          <TabsTrigger value="hours">{t('tabs.hours')}</TabsTrigger>
          <TabsTrigger value="notifications">{t('tabs.notifications')}</TabsTrigger>
          <TabsTrigger value="assistant">{t('tabs.assistant')}</TabsTrigger>
        </TabsList>
        <TabsContent value="profile" className="grid gap-5">
          <ProfileSection />
          <DemoSection />
        </TabsContent>
        <TabsContent value="hours">
          <HoursSection />
        </TabsContent>
        <TabsContent value="notifications">
          <NotificationsSection />
        </TabsContent>
        <TabsContent value="assistant">
          <McpSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}
