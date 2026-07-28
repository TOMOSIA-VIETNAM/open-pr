# Node.js (backend runtime — does not cover JSX/components, see `react.md`)

#### 1. Bugs & logic

- async/await handles errors fully — `try/catch` around `await`, unhandled promise rejection
  avoided (a Promise not `await`-ed/`.catch()`-ed)?
- Callback follows the error-first convention correctly (if callback style is still used)?

#### 2. Security

- `dotenv`/a secret manager used instead of hardcoding secrets?
- Client input validated before entering business logic (Joi/Zod/express-validator, or does manual
  checking miss something)?
- Injection risk (SQL/NoSQL/command injection) through unsanitized input?

#### 3. Performance

- N+1 query via ORM (Sequelize/Prisma/TypeORM) — `include`/eager loading missing?
- Heavy synchronous work (CPU-bound) blocks the event loop? Should offload to a worker
  thread/queue?

#### 4. Code quality

Both `.js` and `.ts` are fully reviewed here; the split below marks which criteria are `.ts`-only.

Applies to both `.js` and `.ts`:

- Module boundaries clear — avoiding circular dependencies, avoiding a "God file" gathering too
  many responsibilities?
- Error objects/custom error classes defined consistently (not throwing strings/objects
  arbitrarily)?

Specific to `.ts` (TypeScript) files:

- Types/interfaces for input, output, DTOs clearly defined, avoiding overuse of `any`?
- Outer layer's type (request body, query params, API/DB response) validated/narrowed to the
  actual runtime type before trusting the static type (avoiding trusting only the declared type
  with no real validation at the boundary)?
- Generic types used sensibly for reusable functions/classes?

#### 5. Node.js specifics

- Structured logging used (Winston/Pino) instead of arbitrary `console.log` in production code?
- Config/env managed centrally (a config module) instead of reading `process.env` scattered
  throughout?
- Middleware/handlers clearly separate responsibilities (routing, validation, business logic, data
  access)?

#### 6. Maintainability & readability

- Tests use Jest/Mocha?
