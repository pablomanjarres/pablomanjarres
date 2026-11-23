# Contribution graphic updates

The daily workflow needs a classic personal access token owned by the profile account, with `repo` and `read:user` scopes. Store it in this repository's Actions secrets as `PROFILE_STATS_TOKEN`.

Create the token in [GitHub developer settings](https://github.com/settings/tokens/new?scopes=repo,read:user&description=PROFILE_STATS_TOKEN), which opens with both scopes selected. The `repo` scope grants access to private repositories; `read:user` enables the private contribution breakdown. Choose a long expiration and replace the secret before it expires: a 30-day token stops the daily refresh on day 31.

Store it from a terminal, pasting the token when prompted:

```bash
gh secret set PROFILE_STATS_TOKEN -R pablomanjarres/pablomanjarres
```

Run **Generate 3D contribution calendar** after adding the secret. A successful refresh requires exact daily totals, no inaccessible contribution types, and complete commit language aggregates. Missing access fails the job before replacing the committed graphic.

When a run fails, the workflow opens an issue titled **Contribution card refresh is failing**, comments on it for each repeat failure, and closes it on the next success. If the fetch step says GitHub rejected the token (HTTP 401), the secret is invalid or expired: create a new token and store it again.

Only contribution dates, counts, language names, and public repository star/fork totals are saved. Private repository identities, source code, and credentials are excluded.
