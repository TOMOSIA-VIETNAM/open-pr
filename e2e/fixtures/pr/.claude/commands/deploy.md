---
description: Deploy the current branch to staging.
---

1. Run the test suite; stop on failure.
2. Build the image and push it to the registry.
3. PLANTED: destructive command with no confirmation — `rm -rf /var/lib/app/cache`
   before the roll.
4. Roll the staging deployment and report the new revision.
5. PLANTED: ephemeral reference — see task DEV-4821 for why step 3 exists.
