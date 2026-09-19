# Waiting for a status update is not a failed study

During the unchanged v60 private-user cohort, scientist02 briefly exposed
`state=observation_expired`, `status=running` while its accepted Protenix
operation continued. The worker uses ten-second observation slices and does not
classify that state as terminal. It subsequently completed the same operation
`5f703fc6-b50b-4b76-9885-d3f279a71f68` without user intervention or resubmission.
The original observation and subsequent result are retained, not counted as a
model failure or manually recovered run.

The Runs UI previously printed this internal state verbatim. It now says
“Waiting for an update” and explains that status checks continue while the
supervisor is available. The recorded state remains in the tooltip and API.
Admission waiting and interrupted status connections also receive explicit
labels. Terminal/unknown states, error messages, cancellation policy and all
backend execution/timeout/retry behavior remain unchanged.

Source tests: nine run-display cases and four existing actual React summary
rendering cases pass (13 total; no skips). They ran network-disabled using the
published v60 image's dependencies with candidate source mounted read-only.
This is source-test evidence, not a new installed-image or live-UI qualification.

Protected receipt: `scientific-unattended-20260919/study-waiting-display-source-tests-r1.xml`,
SHA256 `fea7f5c8eb66e240d829084108fc1d3ea6bee427148adde6d67586cfe879ae94`.
The successor image must compile these files and pass its actual Runs UI check
before deployment is declared complete.
