import { Slot } from '@radix-ui/react-slot';
import { type VariantProps, cva } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import * as React from 'react';
import { cn } from '@/lib/utils';

/** Big buttons: every size has a 44px+ touch target and labels are 18.8px+ bold, so white-on-primary (4.45:1) counts as
 * WCAG "large text" (theme.md §5). Small primary fills use `primary-strong` instead. */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-full text-[1.175rem] font-bold transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:bg-button-disabled disabled:text-muted-foreground disabled:border-transparent select-none',
  {
    variants: {
      variant: {
        default: 'border-2 border-transparent bg-primary text-primary-foreground hover:bg-primary-strong',
        secondary: 'bg-secondary text-secondary-foreground hover:brightness-95',
        outline: 'border-2 border-border bg-card text-foreground hover:bg-muted',
        ghost: 'text-foreground hover:bg-muted',
        danger: 'text-destructive-text hover:bg-error-tint',
        success: 'bg-success text-white hover:brightness-95',
        link: 'text-link underline-offset-4 hover:underline px-0 min-h-0',
      },
      size: {
        default: 'min-h-11 px-5',
        sm: 'min-h-11 px-4',
        lg: 'min-h-14 px-8 text-xl',
        icon: 'size-11',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, disabled, children, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {asChild ? children : (
          <>
            {loading && <Loader2 className="size-5 animate-spin" aria-hidden />}
            {children}
          </>
        )}
      </Comp>
    );
  },
);
Button.displayName = 'Button';

export { buttonVariants };
