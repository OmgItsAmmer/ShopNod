import { getTranslations } from 'next-intl/server';
import { GuardrailsForm } from '@/components/guardrails-form';

export default async function GuardrailsPage() {
  const t = await getTranslations('guardrails');
  return (
    <div className="grid gap-5">
      <div className="grid gap-1">
        <h1 className="text-3xl font-extrabold">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('subtitle')}</p>
      </div>
      <GuardrailsForm />
    </div>
  );
}
