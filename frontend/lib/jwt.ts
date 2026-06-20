// Check if a JWT is expired or invalid
// This utility is Edge-safe and has zero external dependencies.
export function isTokenExpired(token: string | null | undefined): boolean {
  if (!token) return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;

    // Base64Url decode the payload (the second part)
    let payloadStr = parts[1];
    payloadStr = payloadStr.replace(/-/g, '+').replace(/_/g, '/');
    while (payloadStr.length % 4) {
      payloadStr += '=';
    }

    // atob is globally available in browser and next.js edge runtime
    const decoded = atob(payloadStr);
    const payload = JSON.parse(decoded);

    if (payload.exp && typeof payload.exp === 'number') {
      const now = Math.floor(Date.now() / 1000);
      return payload.exp < now;
    }
    return false;
  } catch {
    return true;
  }
}
