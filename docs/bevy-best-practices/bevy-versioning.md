# Bevy versioning policy

> Semi-conservative migration policy for Bevy minor bumps.

---

## Current version

Workspace targets **Bevy 0.18** across all four crates.

Code is already 0.18-canonical: `Message` (the renamed `Event`),
`On<...>` (the renamed `Trigger`), `ChildOf`, `HookContext`,
`MessageReader`, `MessageWriter`, `commands.write_message(...)` are all
in use.

---

## Migration policy (applies to all Bevy version bumps)

**Do not jump to a new Bevy minor on its release.** The dependency
surface — `avian3d`, `bevy-tnua`, `bevy_enhanced_input`,
`bevy_asset_loader`, `bevy_rich_text3d`, `bevy-inspector-egui`,
`bevy_mod_debugdump` — typically lags Bevy main by weeks-to-months.

The **community convention** is to begin patching against a Bevy
release candidate, not the final release. We follow that.

### Protocol

1. **On the next Bevy minor's `-rc` tag**, open a tracking issue
   listing every transitive Bevy-dependent crate and its readiness
   status.
2. **Port internal crates from smallest surface outward**:
   `q_test_harness` → `q_term` / `q_screens` → `quell`.
3. **Deps that are unmaintained or slow to migrate are forked or
   rewritten** rather than blocked on. Forks live as git deps under the
   `cubething-qproj` org with a `q_*` prefix when they become a
   long-term obligation.
4. **The release is considered "adopted"** only when every internal
   crate compiles and tests on the new Bevy without vendored patches
   (or with patches we own).

---

## 0.19 readiness (current next migration)

Anticipated porting tasks, all localized:

- **`set_error_handler` → `set_fallback_error_handler`**
  (and `DefaultErrorHandler` → `FallbackErrorHandler`). Mechanical
  rename in `quell::AppPlugin::build` and any future app entry. See
  [`bevy-error-handling.md`](bevy-error-handling.md).
- **`SystemParam::validate_param` folded into `get_param`** which now
  returns `Result`. Affects `q_screens::data::ScreenInfoRef`,
  `ScreenInfoMut`, `ScreenIdFor` because they manually
  `unsafe impl SystemParam`. Replace `unwrap()` calls in their
  `get_param` impls with `?`.
- **`Resource: Component`** with new `IsResource` filter on broad
  queries. Audit any wide unfiltered queries (we don't expect any).
- **`default_app` slimmed**: `bevy_window` → `common_api`,
  `bevy_input_focus` → `ui_api`, `custom_cursor` → `default_platform`.
  Verify whether `q_test_harness` (which currently has
  `default-features = false, features = ["default_app",
  "default_platform"]`) needs `common_api` added. `q_screens` already
  declares `["default_app", "default_platform", "common_api"]` and is
  future-proof.
- **`bevy_scene` → `bevy_world_serialization`** (and BSN takes the
  `bevy_scene` name). We don't use scenes; no impact.
- **`DespawnOnEnter`/`DespawnOnExit` semantic change** (now fires on
  same-state transitions). We don't use these — `q_screens` owns its
  own `ScreenScoped` invariants. No impact.

---

## What we do not do

- **Track `bevy = { git = "..." }` on main routinely.** The diff churn
  is too high; only the migration spike crate (typically
  `q_test_harness`) tracks main during an active porting cycle.
- **Document the version-rename trail in CONTRIBUTING.md.** The Bevy
  migration guides on bevy.org are the canonical reference. Maintaining
  an in-repo cheatsheet has cost (refresh per release) and small marginal
  benefit. Link to the migration guides; don't duplicate.

---

## When you encounter old Bevy code

If you're reading a tutorial, a Stack Overflow answer, or a third-party
crate that uses pre-0.18 names, the relevant rename storms are:

- **0.15 → 0.16**: `Parent` → `ChildOf`; `EventWriter::send` → `write`;
  required-component syntax change; `StateScoped` → `DespawnOnExit`;
  `PickingBehavior` → `Pickable`; hooks take `HookContext`.
- **0.16 → 0.17**: `Event` → `Message`; `Trigger` → `On`;
  `EventWriter` → `MessageWriter`; `EventReader` → `MessageReader`.
- **0.17 → 0.18**: smaller delta; check the official migration guide.
- **0.18 → 0.19**: see the per-item list above.

Authoritative references: <https://bevy.org/learn/migration-guides/>.
