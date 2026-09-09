# Authentication

Retention Intelligence uses **Auth0 Universal Login** (OAuth 2.0 / OIDC).

```
React  →  Auth0 Universal Login  →  OIDC  →  access token
     →  FastAPI  →  RS256 JWT validation  →  application
```

A valid Auth0 access token is the access mechanism. FastAPI never trusts a
role from the browser (localStorage, React state, query parameters, request
body, or custom headers). The frontend never stores passwords and never
contains an Auth0 client secret.

If the token includes REVIEWER or ADMIN on
`https://retention-intelligence.app/roles`, the TopBar may show that badge.
A missing role does **not** block the application and is **not** filled in
by the backend.

Local URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`

---

## Local Auth0 Configuration

The Vite app binds to `127.0.0.1`. `localhost` and `127.0.0.1` are **different
origins**. Auth0 compares callback, logout, and web-origin URLs as exact
strings. Configure **both**.

This cannot be changed from application code. Add the values in the Auth0
Dashboard → Applications → SPA → Settings.

**Allowed Callback URLs**

```
http://127.0.0.1:5173/callback
http://localhost:5173/callback
```

**Allowed Logout URLs**

```
http://127.0.0.1:5173
http://localhost:5173
```

**Allowed Web Origins**

```
http://127.0.0.1:5173
http://localhost:5173
```

A **Callback URL mismatch** for `http://127.0.0.1:5173/callback` means that
exact string is missing from the SPA settings.

Also:

1. Copy **Domain** into `VITE_AUTH0_DOMAIN` and `AUTH0_DOMAIN`.
2. Copy **Client ID** into `VITE_AUTH0_CLIENT_ID` only. Leave **Client Secret** unused.
3. Enable **Refresh Token Rotation**.

---

## Auth0 API (audience)

The access token `aud` claim must match `VITE_AUTH0_AUDIENCE` and
`AUTH0_AUDIENCE`.

1. Auth0 → Applications → APIs → Create API.
2. Identifier example: `https://telecom-churn-api` (this is not a secret).
3. Signing algorithm: **RS256**.

`AUTH0_ISSUER` can be blank; the backend then uses `https://<AUTH0_DOMAIN>/`.

---

## Application access

| State | Result |
|---|---|
| Unauthenticated | Login page (`Sign in with Auth0` / `Sign up`) |
| Authenticated (valid token) | Full application |
| Authenticated, no role | Full application (no REVIEWER badge) |
| `/api/me` 401 / invalid token | Login |
| API data failure | Page-level API error (session stays signed in) |

Sign up uses Auth0 Universal Login with `screen_hint=signup`. No local
email/password form exists.

`GET /api/me`:

| Token | Result |
|---|---|
| Missing / invalid | 401 |
| REVIEWER | 200, `role: "REVIEWER"` |
| ADMIN | 200, `role: "ADMIN"` |
| Valid token, no role | 200, `role: null` |

Other `/api/*` routes require a valid access token. Invalid or expired JWTs
receive **401**.

---

## Environment variables

Frontend (public):

```
VITE_AUTH0_DOMAIN=
VITE_AUTH0_CLIENT_ID=
VITE_AUTH0_AUDIENCE=https://telecom-churn-api
```

Backend:

```
AUTH0_DOMAIN=
AUTH0_AUDIENCE=https://telecom-churn-api
AUTH0_ISSUER=
AUTH0_ROLES_CLAIM=https://retention-intelligence.app/roles
```

Restart Vite after changing `VITE_*` values.

---

## Production notes

- `APP_ENV=production`
- HTTPS callback, logout, and web origins
- Explicit `CORS_ORIGINS` allowlist (`*` is rejected)
