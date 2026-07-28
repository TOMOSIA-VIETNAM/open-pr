# Laravel (overlay)

_Overlay on top of `php.md`, applied together. Laravel-specific criteria only._

#### 1. Bugs & logic issues

- Migrations safe — a proper `down()` rollback defined, symmetric with `up()`?
- Route model binding used instead of manual queries (`Model::find($id)`) repeated in the
  controller?

#### 2. Security

- Mass assignment configured safely — Model's `$fillable`/`$guarded` declare exactly the right
  fields, avoiding assignment of sensitive fields (`is_admin`, `role`...) through a request?
- Middleware/policies used for authorization, avoiding manual permission checks (if-else) scattered
  through the controller?
- Blade templates escaped correctly — `{{ }}` (auto-escaping) used by default, `{!! !!}` (no
  escaping) only when the data is certainly safe (not user input)?

#### 3. Performance

- Eloquent N+1 queries — relationships accessed in a loop missing `with()`/`load()` eager loading?
- Query builder/scopes used properly instead of loading everything and filtering in PHP (a
  collection)?

#### 4. Code quality

- Form Request (a dedicated `FormRequest` class) used to validate input instead of manual
  validation in the controller?
- Business logic separated from the controller (a Service/Action class) instead of letting the
  controller balloon?

#### 5. Laravel specifics

- Queues/jobs handle errors correctly — retry policy, a `failed()` method, failed jobs
  logged/monitored?
- Events/Listeners and Observers used appropriately for side effects (instead of stuffed into the
  Controller/Model)?
- Config/env accessed via `config()` (cacheable) instead of `env()` directly outside a config file?

#### 6. Maintainability & readability

- Laravel naming convention followed (singular Model, plural Controller, methods named per REST
  resource)?
- Tests correctly distinguish Feature tests (via HTTP) from Unit tests (pure logic)?
