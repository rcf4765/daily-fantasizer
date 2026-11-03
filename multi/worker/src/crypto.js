// Sessions (HMAC-signed cookie), secret storage (AES-GCM) and hashing. No secret ever reaches a page.
const enc = new TextEncoder();
const dec = new TextDecoder();

const b64u = {
  from: (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''),
  to: (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0)),
};

export async function sha256(s) {
  const d = await crypto.subtle.digest('SHA-256', enc.encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function randomId(n = 10) {
  const abc = 'abcdefghjkmnpqrstuvwxyz23456789';
  const r = crypto.getRandomValues(new Uint8Array(n));
  return [...r].map((x) => abc[x % abc.length]).join('');
}

export function randomCode() {  // commissioner code shown once in Settings, e.g. FZ-7KQ2-M9XD
  const abc = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const r = crypto.getRandomValues(new Uint8Array(8));
  const s = [...r].map((x) => abc[x % abc.length]).join('');
  return `FZ-${s.slice(0, 4)}-${s.slice(4)}`;
}

async function hmacKey(secret) {
  return crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}

export async function sign(env, obj) {
  const body = b64u.from(enc.encode(JSON.stringify(obj)));
  const sig = await crypto.subtle.sign('HMAC', await hmacKey(env.SESSION_SECRET), enc.encode(body));
  return `${body}.${b64u.from(sig)}`;
}

export async function verify(env, token) {
  if (!token || !token.includes('.')) return null;
  const [body, sig] = token.split('.');
  const ok = await crypto.subtle.verify('HMAC', await hmacKey(env.SESSION_SECRET), b64u.to(sig), enc.encode(body));
  if (!ok) return null;
  const obj = JSON.parse(dec.decode(b64u.to(body)));
  return obj.exp && obj.exp < Date.now() ? null : obj;
}

async function aesKey(env) {
  const raw = await crypto.subtle.digest('SHA-256', enc.encode(env.ENC_KEY));
  return crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt']);
}

export async function seal(env, text) {
  if (!text) return null;
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await aesKey(env), enc.encode(text));
  return `${b64u.from(iv)}.${b64u.from(ct)}`;
}

export async function open(env, sealed) {
  if (!sealed) return null;
  const [iv, ct] = sealed.split('.');
  const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b64u.to(iv) }, await aesKey(env), b64u.to(ct));
  return dec.decode(pt);
}

export function cookie(req, name) {
  const m = (req.headers.get('Cookie') || '').match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : null;
}

export function setCookie(name, value, maxAgeSec) {
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAgeSec}`;
}

// constant-time-ish compare for the build token
export function same(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let x = 0;
  for (let i = 0; i < a.length; i++) x |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return x === 0;
}

/** Encrypt for the ESPN sign-in job with LOGIN_KEY (shared only with that GitHub job, derived from FZ_MASTER_KEY).
 *  Same format as seal(); the job opens it with open({ ENC_KEY: LOGIN_KEY }, …) from this file. */
export const jobSeal = (env, text) => seal({ ENC_KEY: env.LOGIN_KEY }, text);

/** HMAC-SHA256 hex: the site signs the address it gives a GitHub job, so a job never talks to a look-alike site. */
export async function hmacHex(secret, text) {
  const sig = await crypto.subtle.sign('HMAC', await hmacKey(secret), enc.encode(text));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
