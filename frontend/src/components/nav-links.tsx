"use client";

import { BookOpen, CandlestickChart, PieChart, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/oggi", label: "Oggi", icon: Sun, ready: false },
  { href: "/strumenti", label: "Strumenti", icon: CandlestickChart, ready: true },
  { href: "/portafoglio", label: "Portafoglio", icon: PieChart, ready: false },
  { href: "/diario", label: "Diario", icon: BookOpen, ready: false },
] as const;

type Variant = { variant: "top" | "bottom" };

/** Il percorso corrente arriva in streaming: intanto si mostra il menu senza evidenza. */
export function NavLinks({ variant }: Variant) {
  return (
    <Suspense fallback={<NavList variant={variant} pathname="" />}>
      <ActiveNav variant={variant} />
    </Suspense>
  );
}

function ActiveNav({ variant }: Variant) {
  return <NavList variant={variant} pathname={usePathname()} />;
}

function NavList({ variant, pathname }: Variant & { pathname: string }) {
  const top = variant === "top";
  return (
    <nav
      aria-label="Sezioni"
      className={cn(
        top
          ? "hidden gap-1 sm:flex"
          : "fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t bg-background pb-[env(safe-area-inset-bottom)] sm:hidden",
      )}
    >
      {ITEMS.map(({ href, label, icon: Icon, ready }) => {
        const active = pathname.startsWith(href);
        const classes = cn(
          "transition-colors",
          top
            ? "rounded-sm px-2 py-1 text-sm"
            : "flex h-14 flex-col items-center justify-center gap-1 text-2xs",
          active ? "text-foreground" : "text-muted-foreground",
          ready ? "hover:text-foreground" : "cursor-default text-subtle",
        );
        const content = (
          <>
            {!top && <Icon aria-hidden className="size-5" strokeWidth={1.75} />}
            {label}
          </>
        );
        if (!ready) {
          return (
            <span key={href} aria-disabled="true" title="Disponibile nelle prossime fasi" className={classes}>
              {content}
            </span>
          );
        }
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined} className={classes}>
            {content}
            {top && active && <span className="sr-only">(pagina corrente)</span>}
          </Link>
        );
      })}
    </nav>
  );
}
