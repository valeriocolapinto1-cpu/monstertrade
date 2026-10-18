"use client";

import { usePathname } from "next/navigation";
import { Suspense } from "react";

function Button() {
  if (usePathname().startsWith("/accesso")) return null;
  return (
    <form method="post" action="/accesso/esci" className="ml-auto">
      <button type="submit" className="rounded-sm px-2 py-1 text-xs text-muted-foreground hover:text-foreground">
        Esci
      </button>
    </form>
  );
}

export function LogoutButton() {
  return (
    <Suspense fallback={null}>
      <Button />
    </Suspense>
  );
}
