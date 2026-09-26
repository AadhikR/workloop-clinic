export const migrationPublicConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  oidcAuthority: import.meta.env.VITE_OIDC_AUTHORITY,
  oidcClientId: import.meta.env.VITE_OIDC_CLIENT_ID,
  oidcRedirectUri: import.meta.env.VITE_OIDC_REDIRECT_URI,
  oidcPostLogoutRedirectUri: import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI,
  oidcAudience: import.meta.env.VITE_OIDC_AUDIENCE,
}
