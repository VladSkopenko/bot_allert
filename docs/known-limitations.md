# Deferred work

From review of [the spec](spec.md) (2026-10-30):

- Albums (`grouped_id`) arrive as N separate messages, caption on one only; handlers run concurrently, so a text post can overtake a media post still downloading. Spec lists album grouping under Never.
- Posts published while the process is down (restart, redeploy) are not relayed: StringSession keeps no update state, no catch-up.
- Attachments are downloaded fully into RAM (`file=bytes`); a multi-GB video could OOM the container. No size cap; `cryptg` not installed, so large transfers are slow.
- Docker image runs as root, no lockfile in the image build.
