export const REQUEST_ACCESS_HREF = "#request-access";
export const SIGN_IN_HREF = "#sign-in";

export function gateViewFromHash(hash: string): "request" | "login" | null {
  if (hash === SIGN_IN_HREF) {
    return "login";
  }
  if (hash === REQUEST_ACCESS_HREF) {
    return "request";
  }
  return null;
}
