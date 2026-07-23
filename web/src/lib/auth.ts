import { setApiAccessToken } from "./api";

const authority = import.meta.env.VITE_OIDC_AUTHORITY;
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID;
const audience = import.meta.env.VITE_OIDC_AUDIENCE;
const redirectUri = import.meta.env.VITE_OIDC_REDIRECT_URI || `${window.location.origin}/`;

type OidcModule = typeof import("oidc-client-ts");
type UserManager = InstanceType<OidcModule["UserManager"]>;

let managerPromise: Promise<UserManager> | undefined;

export function isAuthConfigured(): boolean {
  return Boolean(authority && clientId);
}

async function getManager(): Promise<UserManager> {
  if (!isAuthConfigured()) {
    throw new Error("OIDC authentication is not configured.");
  }
  managerPromise ??= import("oidc-client-ts").then(
    ({ UserManager, WebStorageStateStore }) =>
      new UserManager({
        authority: authority!,
        client_id: clientId!,
        redirect_uri: redirectUri,
        post_logout_redirect_uri: `${window.location.origin}/`,
        response_type: "code",
        scope: "openid profile email",
        extraQueryParams: audience ? { audience } : undefined,
        userStore: new WebStorageStateStore({ store: window.sessionStorage }),
        automaticSilentRenew: true,
      }),
  );
  return managerPromise;
}

function removeOidcCallbackParameters(): void {
  const url = new URL(window.location.href);
  ["code", "state", "session_state", "iss"].forEach((key) => url.searchParams.delete(key));
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
}

export async function initialiseAuthentication(): Promise<boolean> {
  if (!isAuthConfigured()) return false;

  const manager = await getManager();
  const callback = new URLSearchParams(window.location.search);
  const user =
    callback.has("code") && callback.has("state")
      ? await manager.signinRedirectCallback()
      : await manager.getUser();
  if (callback.has("code") && callback.has("state")) removeOidcCallbackParameters();

  setApiAccessToken(user && !user.expired ? user.access_token : undefined);
  manager.events.addUserLoaded((loadedUser) => setApiAccessToken(loadedUser.access_token));
  manager.events.addUserUnloaded(() => setApiAccessToken(undefined));
  manager.events.addAccessTokenExpired(() => setApiAccessToken(undefined));
  return Boolean(user && !user.expired);
}

export async function signIn(): Promise<void> {
  const manager = await getManager();
  await manager.signinRedirect({ state: { returnUrl: window.location.href } });
}

export async function signOut(): Promise<void> {
  const manager = await getManager();
  setApiAccessToken(undefined);
  await manager.signoutRedirect();
}
