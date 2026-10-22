# Invite-only Google sign-in

The operator requested Google sign-in with administrator-controlled membership.
Google sign-in is enabled on the current host using the operator-supplied Web
client credentials, with password login disabled at the operator's request. Initial
provider and web/mobile authorization checks pass. The operator confirmed
successful Google login on 2026-10-22; uninvited-account rejection and mobile
browser acceptance are not yet recorded as verified.
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
identity. Google's basic-identity-scope exception means its Testing user list is not a
reliable membership gate for our openid/email/profile scopes. Membership is
enforced in Immich, regardless of Google consent-screen publishing status.

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

## Onboard a new user

1. Sign in with Google as the Immich administrator and open Administration > Users
   > Create user (`/admin/users/new` in the deployed version).
2. Enter the person's name and exact Google account email. This pre-created record
   is their approval to join. Choose an appropriate storage quota in GiB for the
   shared disk; do not grant administrator access for an ordinary user.
3. Leave Password and Confirm password blank. OAuth makes those fields optional
   in the deployed v3.3.5 form. Turn off Require password change on login, then
   create the account. No temporary password needs to be generated or sent.
4. Share `https://immich.xdadwal.in` with the approved person through your normal
   channel. They choose Sign in with Google and select the exact account you
   provisioned. The first successful Google login links that existing user.
5. Confirm the name/account, a representative photo upload/download, the assigned
   quota and, if used, Immich mobile login with the same server URL and Google.

Automatic registration stays disabled. A person with a Google account but no
pre-created Immich user cannot register through sign-in. This is admin-provisioned
membership, not an invitation-token or automatic email system. No SMTP service
is configured; the operator shares the link manually. Creating an Immich user is
sufficient here; no new Google OAuth client is needed for each person.

## Login policy and recovery

Google OAuth is the only enabled interactive login method. Automatic redirects
are disabled so users see the Sign in with Google button. Existing local password
hashes and sessions are preserved, but the password endpoint rejects logins even
with a previously correct password. API-key access used by Homepage still works.
Machine learning stays disabled and auto registration must never be enabled as a
workaround for a mismatched account email.

A failed Google login usually needs checking that the provisioned email matches
the chosen Google account, that the existing account was not already linked to a
different Google identity, and that the Google client redirects/audience settings
are correct. Do not create duplicate accounts or delete users/libraries to repair
account linking. Account deletion also schedules asset deletion, so it is not a
safe generic access-revocation step.

Previous private configurations are retained for operator recovery. If a deliberate
rollback is needed, restore the selected private configuration and force-recreate
only the server using the repository wrapper; do not reset accounts/databases.
The renderer keeps password login disabled whenever it generates a Google OAuth
configuration. The non-secret bootstrap template retains password login solely
for a fresh installation before any Google client is configured; validation
rejects a configuration with both login methods disabled.

## Acceptance

The operator has verified successful Google login. Remaining follow-up checks:
verify Google login/logout with an approved account, rejection
of a Google account that has not been provisioned, unchanged account/library
ownership, rejection of password login, mobile Google login and the Homepage widget.
A healthy container or an authorization URL alone does not prove the Google
client's redirect configuration or invite-only login behavior. Browser login
requires the owner; never claim success from mocked or disposable credentials.

References: [Immich OAuth](https://docs.immich.app/administration/oauth/),
[Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect),
[Google audience rules](https://support.google.com/cloud/answer/15549945),
[pinned user creation form](https://github.com/immich-app/immich/blob/v3.3.5/web/src/routes/admin/users/%28list%29/new/%2Bpage.svelte),
[Google sign-in setup](https://codelabs.developers.google.com/codelabs/sign-in-with-google-button).
