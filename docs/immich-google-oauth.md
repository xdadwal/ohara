# Invite-only Google sign-in

The operator requested Google sign-in with administrator-controlled membership.
Implementation is ready; live Google sign-in remains disabled until the real
Google OAuth client credentials are supplied and browser acceptance succeeds.
Basic Google sign-in uses a free Cloud project; no additional server or shared
authentication service is installed.

## Google-side setup

Create a Google Cloud OAuth client of type Web application. Use the origin
`https://immich.xdadwal.in` and these exact authorized redirect URIs:

```text
https://immich.xdadwal.in/auth/login
https://immich.xdadwal.in/user-settings
https://immich.xdadwal.in/api/oauth/mobile-redirect
```

The last URI handles the mobile application's redirect through Immich. The
requested scopes are only `openid email profile`; no Drive, Gmail or Photos API
access is needed. Complete the consent branding with the operator's actual
identity. A Google app in Testing may also require approved Google test users;
this provider setting is additional to Immich's membership check.

Privately append the actual Google-issued values to the existing `.env`, mode
0600, under `IMMICH_GOOGLE_CLIENT_ID` and `IMMICH_GOOGLE_CLIENT_SECRET`. Never
send them in chat, commit them or put them in the versioned JSON. No client
credentials are generated or invented by Ohara.

## Activate

On this host, retaining the operator's already accepted database-password
exception, run:

```sh
scripts/immich oauth --allow-short-db-password
scripts/immich status
```

The command validates inputs, creates `local/immich/immich.json` with mode 0600
inside a private 0700 directory and recreates only the Immich server. It mounts
this derived configuration read-only instead of the public template; Google
credentials are not passed through Compose environment interpolation and never
reach Homepage, PostgreSQL or media containers. `.env` remains the editable
source. Normal startup preserves the private configuration; after changing the
Google client inputs, rerun the OAuth command explicitly to regenerate it.

Previous derived configurations are backed up privately. If server activation
fails, the command restores the previous configuration and recreates the server
again. Failed candidates are retained privately. Keep these files encrypted
with other recovery material; they contain the OAuth secret. Missing credentials
fail before writing a private config or restarting a container.

## Admit users

`oauth.autoRegister=false` is enforced, including by configuration validation.
An administrator must create each approved Immich user under Administration >
Users using their exact Google email. A Google account with no matching Immich
user is rejected. This is administrator-provisioned membership, not an automated
invitation-email system; no SMTP service or invitation messages are added.

The existing owner's matching Google email can link to the current account.
If the owner uses a different email, sign in with the existing password and use
User Settings to link the intended Google account deliberately. Do not create a
second owner account or reset passwords. Ordinary new accounts should not be
made administrators merely to enable Google sign-in.

Automatic redirect is disabled and existing password login remains available.
The configuration continues to disable all machine-learning services/jobs.
Do not enable auto registration as a workaround for a failed invited-user login.

## Acceptance

After activation verify Google login/logout with an approved account, rejection
of a Google account that has not been provisioned, unchanged account/library
ownership, password fallback, mobile Google login and the Homepage widget.
A healthy container or an authorization URL alone does not prove the Google
client's redirect configuration or invite-only login behavior. Browser login
requires the owner; never claim success from mocked or disposable credentials.

References: [Immich OAuth](https://docs.immich.app/administration/oauth/),
[Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect),
[Google sign-in setup](https://codelabs.developers.google.com/codelabs/sign-in-with-google-button).
