# WordPress (overlay)

_Overlay layered on top of `php.md`, applied together. Lists only WordPress-specific criteria._

#### 1. Bugs & logic issues

- Are hooks/filters used correctly — do `add_action`/`add_filter` declare the correct priority,
  avoiding hidden side effects (running in the wrong order, running multiple times) when the hook
  fires?
- Does the plugin/theme structure hardcode absolute paths, or does it use
  `plugin_dir_path(__FILE__)`/`get_template_directory()` so paths stay correct regardless of
  install location?

#### 2. Security

- Is nonce verification checked for forms/AJAX requests (`wp_verify_nonce`,
  `check_admin_referer`)?
- Is input sanitized before being saved to the DB (`sanitize_text_field`, `sanitize_email`,
  `sanitize_textarea_field`...)?
- Is output escaped before being rendered (`esc_html`, `esc_attr`, `esc_url`...)?
- Is a capability check (`current_user_can`) performed before a sensitive action (deleting/editing
  data, changing a setting)?
- Do DB queries use `$wpdb->prepare` instead of interpolating strings directly into SQL?

#### 3. Performance

- Is `WP_Query`/`get_posts` called repeatedly and unnecessarily inside a loop?
- Is the Transients API/object cache leveraged for expensive-to-compute, rarely-changing data?
- Does meta querying avoid an unnecessary `meta_query` that causes slowness?

#### 4. Code quality

- Are hook callbacks named clearly, avoiding anonymous functions that are hard to unhook when
  needed?

#### 5. WordPress specifics

- Are scripts/styles enqueued correctly — using `wp_enqueue_script`/`wp_enqueue_style` with
  dependencies declared correctly, avoiding echoing `<script>`/`<link>` directly into HTML?
- Does a registered custom post type/taxonomy have all the necessary parameters (labels,
  capability, rewrite)?
- Does it avoid namespace/global function/hook name conflicts with other plugins/themes (using its
  own prefix)?

#### 6. Maintainability & readability

- Is the dependency order between hooks (what runs before/after, which priority) clearly noted?
- Does the coding standard follow the WordPress Coding Standards (WPCS)?
- Is the design resilient to WordPress core/other plugin updates (avoiding reliance on
  undocumented internal behavior)?
