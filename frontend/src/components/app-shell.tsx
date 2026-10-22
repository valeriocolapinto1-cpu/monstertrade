import Link from "next/link";

import { LogoutButton } from "@/components/logout-button";
import { NavLinks } from "@/components/nav-links";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col pb-[calc(3.5rem+env(safe-area-inset-bottom))] sm:pb-0">
      {/* Nell'app installata la barra di stato è trasparente: l'intestazione parte sotto di essa. */}
      <header className="sticky top-0 z-20 border-b bg-background/95 pt-[env(safe-area-inset-top)] backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex h-12 max-w-7xl items-center gap-6 pr-[max(1rem,env(safe-area-inset-right))] pl-[max(1rem,env(safe-area-inset-left))]">
          <Link
            href="/oggi"
            className="flex items-center gap-2 text-base font-semibold tracking-tight"
          >
            <Logo />
            MonsterTrade
          </Link>
          <NavLinks variant="top" />
          <LogoutButton />
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 py-5 pr-[max(1rem,env(safe-area-inset-right))] pl-[max(1rem,env(safe-area-inset-left))] sm:py-6">{children}</main>
      <footer className="border-t">
        <p className="mx-auto max-w-7xl px-4 py-3 text-2xs text-subtle">
          Strumento informativo per uso personale, non costituisce consulenza finanziaria. I
          rendimenti passati non sono indicativi di quelli futuri.
        </p>
      </footer>
      <NavLinks variant="bottom" />
    </div>
  );
}

function Logo() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="size-4 text-primary">
      <path
        d="M1 11.5 5 7l3 3 4-5.5L15 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
