# Contribution graphic updates

The daily workflow needs a classic personal access token owned by the profile account, with `repo` and `read:user` scopes. Store it in this repository's Actions secrets as `PROFILE_STATS_TOKEN`.

Create the token in [GitHub developer settings](https://github.com/settings/tokens/new). The `repo` scope grants access to private repositories; `read:user` enables the private contribution breakdown. Choose an expiration date and replace the secret before it expires.

Run **Generate 3D contribution calendar** after adding the secret. A successful refresh requires exact daily totals, no inaccessible contribution types, and complete commit language aggregates. Missing access fails the job before replacing the committed graphic.

Only contribution dates, counts, language names, and public repository star/fork totals are saved. Private repository identities, source code, and credentials are excluded.
