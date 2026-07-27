# Vue 2/3, Nuxt

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Is error handling for async operations (Promise, async/await, axios) appropriate?
- Is data from an API validated before being rendered?

#### 2. Security

- Is there an XSS risk via `v-html` (user input data not escaped)?
- Check that the `.env` file isn't committed.
- Do API calls attach the correct authentication token?

#### 3. Performance

- Is there unnecessary re-rendering? Check for `computed` instead of `methods` for reactive
  derived values.
- Does `v-for` use `:key` correctly (not using the index as the key when the list's order can
  change)?
- Is the Component instance destroyed correctly in `beforeDestroy`?
- Are images and static assets optimized?

#### 4. Code quality

- Consider extracting duplicated code into a mixin or composable.
- Are TypeScript types defined correctly (not overusing `any`)? Interfaces should live in the
  `interfaces/` directory.
- Are constants placed in the `constants/` directory?
- Are utility functions placed in the `utils/` directory?

#### 5. Nuxt 2 / Vue 2 specifics

- **Component**: Is the `@Component` decorator (nuxt-property-decorator) used correctly? Are
  `@Prop`, `@Watch`, `@Emit` used instead of the plain Options API?
- **Vuex**: Are actions/mutations/getters placed in the correct module? Avoid committing a
  mutation directly from a component, use an action instead.
- **Routing**: Is `nuxt-link` used instead of `router-link`, does `this.$router.push` handle
  errors?
- **Lifecycle hooks**: Are `mounted` vs `created` used in the correct context (SSR-aware)? Avoid
  DOM access in `created`.
- **API calls**: Is `@nuxtjs/axios` (`this.$axios`) used consistently? Does error handling use
  try/catch or `.catch()`?
- **Ant Design Vue**: Are component imports correct? Do event listeners use `@change` / `@click`
  instead of plain `v-on`?
- **SCSS**: Is the style scoped (`<style scoped>`)? Avoid unnecessary global style overrides. Are
  SCSS variables imported from `assets/`?
- **nuxt.config.js**: If the config changed, check that plugins/modules are registered correctly,
  avoid adding a heavy library into the global `head`.

#### 6. Maintainability & readability

- Is the component too large? Should be split up if it exceeds ~300 lines.
- Does ESLint/Prettier pass? There should be no `// eslint-disable` without a reason.
