# Professional Capture lifecycle acceptance note

This PR is acceptable only if automated tests prove that:

1. successful capture attempts do not close the capture page;
2. non-auth capture exceptions do not call the persistent browser shutdown function;
3. non-auth capture exceptions do not close the capture page;
4. login-required retry behavior remains intact.

The first real LinkedIn run after merge should test browser persistence first, not candidate import quality.
