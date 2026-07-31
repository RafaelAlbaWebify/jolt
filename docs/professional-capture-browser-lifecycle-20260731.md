# Professional Capture browser lifecycle contract

Date: 2026-07-31

## Problem fixed

The user-present LinkedIn workflow depends on Chromium staying open after a capture attempt. The browser window is part of the workflow: the user needs to inspect failures, complete LinkedIn login/checkpoint steps, and retry from JOLT.

Previous behavior closed the capture page after most attempts and reset the whole persistent browser context after non-auth capture exceptions. That made real captures appear to collapse immediately after launch.

## Lifecycle contract

Professional Capture must keep the persistent Chromium context and capture page open after:

- successful capture;
- partial capture;
- readiness timeout;
- LinkedIn login/checkpoint/authwall detection;
- non-auth browser/navigation/DOM/screenshot exception.

Professional Capture may close Chromium only when:

- the backend process exits and the registered shutdown handler runs;
- a future explicit user-facing action requests browser closure;
- a future validated recovery path determines that the context is already unrecoverable before a new capture starts.

## Diagnostics contract

A failed capture should still preserve useful evidence where possible:

- source-level progress detail;
- attempted URL;
- final URL when available;
- page title when available;
- error class and message;
- `page-diagnostics.json` when the evidence root can be written.

The UI should expose source progress and failure details instead of showing only a generic failed run.
