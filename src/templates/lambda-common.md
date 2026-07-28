# AWS Lambda (serverless — overlay)

_Overlay on top of the base language template (`python.md` for a Python handler, `nodejs.md` for a
Node.js handler), applied together when reviewing a lambda handler. Serverless-specific criteria
only._

#### 1. Bugs & logic issues

- Idempotency guaranteed on Lambda retry — side effects (DB write, external API call, publishing a
  message) safe when the handler is invoked again with the same event?
- Batch event handling (SQS/SNS/Kinesis/DynamoDB Streams) handles partial failure correctly —
  returns the correct failed item (batch item failure) instead of failing the entire batch, if the
  framework/runtime supports it?

#### 2. Security

- IAM policy (`serverless.yml`/`template.yaml`/SAM) follows least-privilege — `*` used carelessly
  for actions/resources?
- Sensitive env vars (API key, connection string, secret) fetched via Parameter Store/Secrets
  Manager instead of hardcoded in plaintext config/env?

#### 3. Performance

- Cold start optimized — heavy init (DB connections, SDK client loading, model loading) at
  module-level/global scope instead of inside the handler (re-initialized every invoke)?
- Timeout config reasonable relative to actual execution time (not too short ⇒ false timeouts, not
  too long ⇒ wasted cost on a hang)?
- Memory sizing appropriate for the workload (too low ⇒ slowness/OOM, too high ⇒ wasted cost)?
- Deployment package/layer size kept in check (oversized package worsens cold start)?

#### 4. Code quality

- Infra config (`serverless.yml`/`template.yaml`/SAM) split by environment (dev/staging/prod),
  avoiding hardcoded environment-specific values?
- Handler clearly separates "adapter" (parsing the event, formatting the response) from pure
  business logic, testable independently of the Lambda runtime?

#### 5. Lambda/serverless specifics

- Structured logging suited to CloudWatch (JSON-formatted, includes a request id/correlation id to
  trace by invocation)?
- Layers/dependencies shared across functions split out via a Lambda Layer instead of duplicated
  per package?
- Triggers/event source mappings (API Gateway, SQS, EventBridge, S3...) configured correctly
  (batch size, concurrency limit, a DLQ for failed messages)?

#### 6. Maintainability & readability

- Comment explaining why a specific memory/timeout/concurrency value was chosen (if unusual)?
- Design flexible enough to add a new trigger/event source in the future?
