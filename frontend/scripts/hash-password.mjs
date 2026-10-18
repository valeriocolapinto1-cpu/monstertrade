// Uso: node scripts/hash-password.mjs   (chiede la password senza mostrarla)
// Stampa il valore da mettere in APP_PASSWORD_HASH su Vercel.
import { randomBytes, scryptSync } from "node:crypto";
import { stdin, stdout } from "node:process";

stdout.write("Password: ");
stdin.setRawMode?.(true);
let input = "";
stdin.on("data", (chunk) => {
  for (const ch of chunk.toString()) {
    if (ch === "\r" || ch === "\n") {
      stdin.setRawMode?.(false);
      stdout.write("\n");
      if (input.length < 12) {
        console.error("Usa almeno 12 caratteri.");
        process.exit(1);
      }
      const N = 2 ** 15, r = 8, p = 1;
      const salt = randomBytes(16);
      const key = scryptSync(input.normalize("NFKC"), salt, 32, { N, r, p, maxmem: 64 * 1024 * 1024 });
      console.log(["scrypt", N, r, p, salt.toString("base64"), key.toString("base64")].join("$"));
      console.log("\nSESSION_SECRET suggerito:", randomBytes(32).toString("base64url"));
      process.exit(0);
    } else if (ch === "\u0003") {
      process.exit(1);
    } else {
      input += ch;
    }
  }
});
