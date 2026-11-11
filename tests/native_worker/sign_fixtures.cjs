"use strict";

const { generateKeyPairSync, sign } = require("node:crypto");
const { publicKey, privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const rotation = generateKeyPairSync("rsa", { modulusLength: 2048 });
const rotationKid = "native-rotation-fixture";
const now = Math.floor(Date.now() / 1000);
const tokens = {};
function tokenFor(name, overrides = {}, key = privateKey, header = {}) {
  const head = Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT", ...header })).toString("base64url");
  const body = Buffer.from(JSON.stringify({
    sub: "user_native_" + name, sid: "sess_native_" + name,
    exp: now + 600, nbf: now - 5, ...overrides
  })).toString("base64url");
  const input = head + "." + body;
  return input + "." + sign("RSA-SHA256", Buffer.from(input), key).toString("base64url");
}
for (const name of ["client", "contractor", "other_client", "other_contractor", "admin", "suspended",
                    "onboarding", "onboarding_conflict", "onboarding_restricted"]) {
  tokens[name] = tokenFor(name);
}
tokens.expired = tokenFor("client", { exp: now - 60 });
tokens.wrong_origin = tokenFor("client", { azp: "https://untrusted.invalid" });
tokens.pending = tokenFor("client", { sts: "pending" });
const parts = tokens.client.split(".");
parts[2] = (parts[2][0] === "A" ? "B" : "A") + parts[2].slice(1);
tokens.invalid_signature = parts.join(".");
tokens.rotated = tokenFor("client", {}, rotation.privateKey, { kid: rotationKid });
tokens.unknown_key = tokenFor("client", {}, rotation.privateKey, { kid: "untrusted-fixture" });
process.stdout.write(JSON.stringify({
  public_key: publicKey.export({ type: "spki", format: "pem" }),
  rotation_jwk: { ...rotation.publicKey.export({ format: "jwk" }), kid: rotationKid },
  tokens
}));
