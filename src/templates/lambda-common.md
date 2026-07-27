# AWS Lambda (serverless — overlay)

_Overlay layered on top of the base language template (`python.md` for a Python handler,
`nodejs.md` for a Node.js handler), applied together when reviewing a lambda handler. Lists only
serverless-specific criteria._

#### 1. Bugs & logic issues

- Is idempotency guaranteed when a Lambda gets retried — are side effects (writing to a DB,
  calling an external API, publishing a message) safe when the handler gets invoked again with the
  same event?
- Does batch event handling (SQS/SNS/Kinesis/DynamoDB Streams) correctly handle partial failure —
  does it return the correct failed item (batch item failure) instead of failing the entire batch,
  if the framework/runtime supports it?

#### 2. Security

- Does the IAM policy in `serverless.yml`/`template.yaml`/SAM follow least-privilege — does it use
  `*` for actions/resources carelessly?
- Are sensitive env vars (API key, connection string, secret) fetched via Parameter Store/Secrets
  Manager instead of hardcoded in plaintext config/env?

#### 3. Performance

- Is cold start optimized — is heavy initialization logic (DB connections, loading SDK clients,
  loading a model) placed at module-level/global scope instead of inside the handler (re-
  initialized on every invoke)?
- Is the timeout config reasonable relative to the actual execution time of the logic inside (not
  too short causing false timeouts, not too long wasting cost on a hang)?
- Is memory sizing appropriate for the workload (too low causes slowness/OOM, too high wastes
  cost)?
- Is the deployment package/layer size kept in check (avoiding an oversized package that makes
  cold start worse)?

#### 4. Code quality

- Is infrastructure config (`serverless.yml`/`template.yaml`/SAM) properly split by environment
  (dev/staging/prod), avoiding hardcoded environment-specific values?
- Does the handler clearly separate the "adapter" part (parsing the event, formatting the
  response) from pure business logic, so it can be tested independently of the Lambda runtime?

#### 5. Lambda/serverless specifics

- Is structured logging suited to CloudWatch (JSON-formatted logs, including a request id/
  correlation id to trace by invocation)?
- Are layers/dependencies shared across multiple functions split out via a Lambda Layer instead of
  duplicated in each package?
- Are triggers/event source mappings (API Gateway, SQS, EventBridge, S3...) configured correctly
  (batch size, concurrency limit, a DLQ for failed messages)?

#### 6. Maintainability & readability

- Is there a comment explaining why a specific memory/timeout/concurrency value was chosen (if the
  value is unusual)?
- Is the design flexible enough to add a new trigger/event source in the future?
