# Professional capture LinkedIn session behavior

JOLT uses a visible, persistent Chromium profile for Professional Intelligence capture.

The profile is stored locally at:

```text
backend/data/professional-browser-profile
```

This directory is intentionally separate from governed capture evidence. It stores browser session state so the user can sign in to LinkedIn once in the visible browser and reuse that session for later supervised read-only captures.

If LinkedIn redirects to an authwall, signup, or login page, JOLT treats that as an authentication failure rather than successful partial evidence. The visible browser remains open long enough for the user to complete sign-in. If the page is still an authwall after the sign-in wait, the run fails with a clear diagnostic and the user can rerun capture after confirming the browser profile is signed in.

This workflow does not store LinkedIn credentials in JOLT. Credentials are entered only by the user into the visible Chromium browser profile.
