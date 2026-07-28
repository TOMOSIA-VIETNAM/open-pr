# WordPress (overlay)

_Overlay on top of `php.md`, applied together. WordPress-specific criteria only._

#### 1. Bugs & logic issues

- Hooks/filters used correctly — `add_action`/`add_filter` declare the correct priority, avoiding
  hidden side effects (wrong order, running multiple times) when the hook fires?
- Plugin/theme structure hardcodes absolute paths, or uses
  `plugin_dir_path(__FILE__)`/`get_template_directory()` so paths stay correct regardless of
  install location?

#### 2. Security

- Nonce verification checked for forms/AJAX requests (`wp_verify_nonce`, `check_admin_referer`)?
- Input sanitized before being saved to the DB (`sanitize_text_field`, `sanitize_email`,
  `sanitize_textarea_field`...)?
- Output escaped before being rendered (`esc_html`, `esc_attr`, `esc_url`...)?
- Capability check (`current_user_can`) performed before a sensitive action (deleting/editing
  data, changing a setting)?
- DB queries use `$wpdb->prepare` instead of interpolating strings directly into SQL?

#### 3. Performance

- `WP_Query`/`get_posts` called repeatedly and unnecessarily inside a loop?
- Transients API/object cache leveraged for expensive-to-compute, rarely-changing data?
- Meta querying avoids an unnecessary `meta_query` that causes slowness?

#### 4. Code quality

- Hook callbacks named clearly, avoiding anonymous functions hard to unhook when needed?

#### 5. WordPress specifics

- Scripts/styles enqueued correctly — `wp_enqueue_script`/`wp_enqueue_style` with dependencies
  declared correctly, avoiding echoing `<script>`/`<link>` directly into HTML?
- Registered custom post type/taxonomy has all necessary parameters (labels, capability, rewrite)?
- Avoids namespace/global function/hook name conflicts with other plugins/themes (own prefix)?

#### 6. Maintainability & readability

- Dependency order between hooks (what runs before/after, which priority) clearly noted?
- Coding standard follows the WordPress Coding Standards (WPCS)?
- Design resilient to WordPress core/other plugin updates (avoiding reliance on undocumented
  internal behavior)?
