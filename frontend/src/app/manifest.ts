import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MonsterTrade",
    short_name: "MonsterTrade",
    description: "Analisi tecnica e sentiment per uso personale",
    lang: "it",
    start_url: "/strumenti",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#0a0d13",
    theme_color: "#0a0d13",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
