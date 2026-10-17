import { Slot } from '@radix-ui/react-slot';
import * as React from 'react';
import { cn } from '@/lib/utils';

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div data-ui="card" className={cn('overflow-hidden rounded-[1.5rem] border border-border bg-card text-card-foreground shadow-sm', className)} {...props} />;
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div data-ui="card-header" className={cn('flex flex-col gap-1 border-b border-border p-6 pb-4', className)} {...props} />;
}

export function CardTitle({ className, asChild = false, ...props }: React.HTMLAttributes<HTMLHeadingElement> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'h2';
  return <Comp className={cn('text-2xl font-bold leading-[1.05] tracking-[-0.035em]', className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-base text-muted-foreground', className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div data-ui="card-content" className={cn('p-6', className)} {...props} />;
}

export function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-wrap items-center gap-3 border-t border-border p-6 pt-4', className)} {...props} />;
}
