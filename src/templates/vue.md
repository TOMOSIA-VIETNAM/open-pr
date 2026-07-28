# Vue 2/3, Nuxt

_Additions to the `ALWAYS_RULE.md` baseline; stack-specific criteria only, does not repeat the
baseline._

#### 1. Bugs & logic issues

- Error handling for async operations (Promise, async/await, axios) appropriate?
- Data from an API validated before being rendered?

#### 2. Security

- XSS risk via `v-html` (user input not escaped)?
- `.env` file not committed.
- API calls attach the correct authentication token?

#### 3. Performance

- Unnecessary re-rendering? `computed` used instead of `methods` for reactive derived values?
- `v-for` uses `:key` correctly (not the index as key when the list's order can change)?
- Component instance destroyed correctly in `beforeDestroy`?
- Images and static assets optimized?

#### 4. Code quality

- Consider extracting duplicated code into a mixin or composable.
- TypeScript types defined correctly (not overusing `any`)? Interfaces live in `interfaces/`.
- Constants placed in `constants/`.
- Utility functions placed in `utils/`.

#### 5. Nuxt 2 / Vue 2 specifics

- **Component**: `@Component` decorator (nuxt-property-decorator) used correctly? `@Prop`,
  `@Watch`, `@Emit` used instead of the plain Options API?
- **Vuex**: Actions/mutations/getters placed in the correct module? Avoid committing a mutation
  directly from a component, use an action instead.
- **Routing**: `nuxt-link` used instead of `router-link`? Does `this.$router.push` handle errors?
- **Lifecycle hooks**: `mounted` vs `created` used in the correct context (SSR-aware)? Avoid DOM
  access in `created`.
- **API calls**: `@nuxtjs/axios` (`this.$axios`) used consistently? Error handling via try/catch
  or `.catch()`?
- **Ant Design Vue**: Component imports correct? Event listeners use `@change` / `@click` instead
  of plain `v-on`?
- **SCSS**: Style scoped (`<style scoped>`)? Avoid unnecessary global style overrides. SCSS
  variables imported from `assets/`?
- **nuxt.config.js**: Config changed → plugins/modules registered correctly? Avoid adding a heavy
  library into the global `head`.

#### 6. Maintainability & readability

- Component too large? Should split up if it exceeds ~300 lines.
- ESLint/Prettier passes? No `// eslint-disable` without a reason.
