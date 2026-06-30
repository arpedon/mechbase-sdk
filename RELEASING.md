# Releasing the Mechbase SDKs

All four SDKs live in this one repo but version and ship independently. Each is
released by pushing a **tag** — CI (`.github/workflows/`) does the rest.

| SDK    | Tag to push    | Goes to                          | Consumer pulls from                                    |
|--------|----------------|----------------------------------|--------------------------------------------------------|
| Python | `python/vX.Y.Z`| PyPI (`mechbase`)                | `pip install mechbase`                                 |
| Kotlin | `kotlin/vX.Y.Z`| Maven Central (`com.arpedon`)    | `implementation("com.arpedon:mechbase-sdk:X.Y.Z")`     |
| Go     | `go/vX.Y.Z`    | GitHub (via Go module proxy)     | `go get github.com/arpedon/mechbase-sdk/go@vX.Y.Z`     |
| Swift  | `vX.Y.Z` (bare)| GitHub (via SwiftPM)             | `.package(url: ".../mechbase-sdk", from: "X.Y.Z")`     |

> The tag prefixes keep the SDKs independent. SwiftPM only recognizes **bare**
> semver tags (`v0.2.0`) and ignores the prefixed ones, so Swift owns the bare
> tag and the others are namespaced.

---

## One-time setup (per language)

### Go & Swift — nothing to host

No registry, no account, no secrets. Both pull straight from this Git repo via
their toolchains' module proxies. The only requirement:

- **Repo must be public** (or each consumer sets `GOPRIVATE=github.com/arpedon/*`
  for Go / uses an SSH dependency URL for Swift).

That's it — once a tag is pushed, `go get` / SwiftPM can resolve it immediately.

### Python — PyPI trusted publishing (no tokens)

1. On <https://pypi.org/org/arpedon/>, claim/create the **`mechbase`** project
   (first publish can also create it, but claiming it under the org first keeps
   ownership clean).
2. Project → **Settings → Publishing → Add a trusted publisher** (GitHub):
   - Owner: `arpedon`
   - Repository: `mechbase-sdk`
   - Workflow name: `publish-python.yml`
   - Environment: *(leave blank)*

No API tokens, no GitHub secrets. OIDC handles auth.

### Kotlin — Maven Central (Sonatype Central Portal)

1. **Account + namespace.** Sign in at <https://central.sonatype.com>. Register
   the **`com.arpedon`** namespace and verify it by adding the DNS `TXT` record
   they show you to the **arpedon.com** domain.
   - *No control of arpedon.com?* Use namespace **`io.github.arpedon`** instead
     (verified by creating a one-off public repo they name), and change `group`
     in `kotlin/build.gradle.kts` to `io.github.arpedon`.
2. **User token.** Central Portal → your name → **Generate User Token**. You get
   a username + password pair (these are the token, not your login).
3. **GPG signing key** (Central requires signed artifacts):
   ```bash
   gpg --quick-generate-key "Arpedon <dev@arpedon.com>" rsa4096 sign 2y
   gpg --list-secret-keys --keyid-format=long          # note the KEY_ID
   gpg --keyserver keyserver.ubuntu.com --send-keys KEY_ID   # publish public half
   gpg --armor --export-secret-keys KEY_ID             # the value for SIGNING_KEY
   ```
4. **GitHub secrets** (repo → Settings → Secrets and variables → Actions):

   | Secret                   | Value                                              |
   |--------------------------|----------------------------------------------------|
   | `MAVEN_CENTRAL_USERNAME` | Central Portal user-token **username**             |
   | `MAVEN_CENTRAL_PASSWORD` | Central Portal user-token **password**             |
   | `SIGNING_KEY`            | full ASCII-armored secret key (the `gpg --armor` block) |
   | `SIGNING_KEY_PASSWORD`   | passphrase for that key (empty if none)            |

> First Kotlin release: namespace verification must be **approved** before the
> publish step can succeed, or it fails with a 403. The workflow uses
> `publishAndReleaseToMavenCentral` (auto-release). To gate the first one
> manually, temporarily swap it to `publishToMavenCentral` and click **Publish**
> in the portal.

---

## Dry-run a Kotlin release first (recommended)

`publishToMavenCentral` (note: **not** `...AndRelease`) uploads a *staging*
deployment you can inspect and **drop** — it validates signing, auth, the POM,
and namespace ownership without releasing anything irreversibly:

```bash
cd kotlin                                   # on a branch whose version is the one you'll cut
read -rs -p "GPG passphrase: " PASS; echo   # keeps the passphrase off-screen/out of history
ORG_GRADLE_PROJECT_mavenCentralUsername=<token-user> \
ORG_GRADLE_PROJECT_mavenCentralPassword=<token-pass> \
ORG_GRADLE_PROJECT_signingInMemoryKeyPassword="$PASS" \
ORG_GRADLE_PROJECT_signingInMemoryKey="$(gpg --batch --pinentry-mode loopback --passphrase "$PASS" --armor --export-secret-keys KEY_ID)" \
./gradlew publishToMavenCentral --no-configuration-cache
```

`BUILD SUCCESSFUL` means the pipeline is sound. Drop the staging deployment at
<https://central.sonatype.com> → **Deployments** (it won't auto-release), then
push the tag below for the real, auto-released run.

## Cutting a release

Bump the version **in the manifest**, commit, then tag. CI checks the tag matches
the manifest for Python/Kotlin and fails on mismatch.

```bash
# Python  — edit version in python/pyproject.toml
git commit -am "release python 0.2.1"
git tag python/v0.2.1 && git push origin main python/v0.2.1

# Kotlin  — edit version in kotlin/build.gradle.kts
git commit -am "release kotlin 0.2.3"
git tag kotlin/v0.2.3 && git push origin main kotlin/v0.2.3

# Go      — no manifest version; the tag IS the version
git tag go/v0.2.0 && git push origin go/v0.2.0

# Swift   — no manifest version; the bare tag IS the version
git tag v0.2.0 && git push origin v0.2.0
```

After PyPI/Maven Central publishes, the package may take a few minutes to be
installable (PyPI is near-instant; Maven Central sync can take ~10–30 min).

**Verify it landed:**

| SDK    | Where to check                                                              |
|--------|-----------------------------------------------------------------------------|
| Kotlin | central.sonatype.com → **Deployments** (state *Published*), then synced to <https://repo1.maven.org/maven2/com/arpedon/mechbase-sdk/> |
| Python | <https://pypi.org/project/mechbase/>                                        |
| Go     | `go list -m github.com/arpedon/mechbase-sdk/go@vX.Y.Z`                      |
| Swift  | `git ls-remote --tags` shows the bare tag; SwiftPM resolves it             |

> A green `publish-*` workflow run is the authoritative "it released" signal —
> the registry's own published/search index can lag the workflow by minutes.
> The freshly-published Maven Central `published?...` API likewise flips to
> `true` only after repo1 sync, not the instant the workflow finishes.
