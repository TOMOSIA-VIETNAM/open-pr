# Laravel (overlay)

_Overlay layered on top of `php.md`, applied together. Lists only Laravel-specific criteria._

#### 1. Bugs & logic issues

- Are migrations safe — is a proper `down()` rollback method defined, symmetric with `up()`?
- Is route model binding used instead of manual queries (`Model::find($id)`) repeated in the
  controller?

#### 2. Security

- Is mass assignment configured safely — do the Model's `$fillable`/`$guarded` declare exactly the
  right fields, avoiding assignment of sensitive fields (`is_admin`, `role`...) through a request?
- Are middleware/policies used for authorization, avoiding manual permission checks (if-else)
  scattered through the controller?
- Are Blade templates escaped correctly — is `{{ }}` (auto-escaping) used by default, with
  `{!! !!}` (no escaping) used only when the data is certainly safe (not user input)?

#### 3. Performance

- Does Eloquent suffer from N+1 queries — are relationships accessed in a loop missing
  `with()`/`load()` eager loading?
- Does the query make proper use of the query builder/scopes instead of loading everything and
  filtering in PHP (a collection)?

#### 4. Code quality

- Is a Form Request (a dedicated `FormRequest` class) used to validate input instead of manual
  validation in the controller?
- Is business logic separated from the controller (a Service/Action class) instead of letting the
  controller balloon?

#### 5. Laravel specifics

- Do queues/jobs handle errors correctly — retry policy, a `failed()` method, are failed jobs
  logged/monitored?
- Are Events/Listeners and Observers used appropriately for side effects (instead of stuffed into
  the Controller/Model)?
- Is config/env accessed via `config()` (cacheable) instead of `env()` directly outside a config
  file?

#### 6. Maintainability & readability

- Is Laravel's naming convention followed (singular Model, plural Controller, methods named per
  REST resource)?
- Do tests correctly distinguish Feature tests (via HTTP) from Unit tests (pure logic)?
