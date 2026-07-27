# Node.js (backend runtime — does not cover JSX/components, see `react.md`)

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Does async/await handle errors fully — is there a `try/catch` around `await`, is an unhandled
  promise rejection avoided (a Promise not `await`-ed/`.catch()`-ed)?
- Does a callback follow the error-first convention correctly (if callback style is still used)?

#### 2. Security

- Is `dotenv`/a secret manager used instead of hardcoding secrets?
- Is input from the client validated before entering business logic (Joi/Zod/express-validator, or
  is manual checking missing something)?
- Is there an injection risk (SQL/NoSQL/command injection) through unsanitized input?

#### 3. Performance

- Is there an N+1 query issue when using an ORM (Sequelize/Prisma/TypeORM) — is `include`/eager
  loading missing?
- Does heavy synchronous work (CPU-bound) block the event loop? Should it be offloaded to a worker
  thread/queue?

#### 4. Code quality

JavaScript and TypeScript are 2 equally valid base languages for the Node.js backend in this
project (both `.js` and `.ts` are fully reviewed) — the criteria below clearly split what applies
generally versus what applies only when the file is TypeScript.

Applies to both `.js` and `.ts`:

- Are module boundaries clear — avoiding circular dependencies, avoiding a "God file" that gathers
  too many responsibilities?
- Are error objects/custom error classes defined consistently (not throwing strings/objects
  arbitrarily)?

Specific to `.ts` (TypeScript) files:

- Are types/interfaces for input, output, and DTOs clearly defined, avoiding overuse of `any`?
- Is the outer layer's type (request body, query params, API/DB response) validated/narrowed to
  the actual runtime type before trusting the static type (avoiding trusting only the declared
  type with no real validation at the boundary)?
- Are generic types used sensibly for reusable functions/classes?

#### 5. Node.js specifics

- Is structured logging used (Winston/Pino) instead of arbitrary `console.log` calls in production
  code?
- Is config/env managed centrally (a config module) instead of reading `process.env` scattered
  throughout?
- Do middleware/handlers clearly separate responsibilities (routing, validation, business logic,
  data access)?

#### 6. Maintainability & readability

- Do tests use Jest/Mocha?
