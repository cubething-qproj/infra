# Bevy conventions

> Plugin shape, module layout, observers, bundles, `Startup` rules.

---

## Plugin shape

### Function-as-plugin for internals; struct-as-plugin for exports

```rust
// quell/src/screen/splash/mod.rs
pub(super) fn plugin(app: &mut App) {
    app.add_systems(Update, (your, systems, here));
}

// quell/src/screen/mod.rs
pub(super) fn plugin(app: &mut App) {
    app.add_plugins((splash::plugin, world::plugin));
}
```

```rust
// q_term/src/plugin.rs
#[derive(Default, Debug)]
pub struct TerminalPlugin;
impl Plugin for TerminalPlugin {
    fn build(&self, app: &mut App) {
        app.add_message::<TermMsg>();
        // ...
    }
}
```

**Why the split:** stable struct identity lets a library evolve
configuration without a SemVer break. Application internals don't ship
to consumers, so they don't need that protection — function-as-plugin
keeps the call site terse.

### One plugin per file

A `mod.rs` (or leaf `.rs`) exports exactly one `plugin` symbol. Empty
plugins are omitted entirely.

### Public `SystemSet` enum is mandatory for shared-schedule plugins

If your library plugin adds systems to `Update`, `FixedUpdate`,
`PostUpdate`, `PreUpdate`, `FixedPostUpdate`, etc., it **must** export
a public `SystemSet` enum and register all its systems `.in_set(...)`:

```rust
#[derive(SystemSet, Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub struct TerminalSystems;

// In Plugin::build:
app.add_systems(
    PostUpdate,
    (update_font, update_char_width, /* ... */)
        .chain()
        .after(ui_layout_system)
        .in_set(TerminalSystems),
);
```

- Single-variant marker sets are fine for minimal contracts (cf. avian's
  `TnuaUserControlsSystems`).
- Add `PartialOrd, Ord` to the derive if the variants are
  `.chain()`-ordered.
- Multi-schedule plugins MAY publish multiple sets
  (`FooStartupSystems`, `FooUpdateSystems`, `FooPostUpdateSystems`).
- Consumers order against the set, not against your internal system
  items.

### Configurable schedule via `::new(schedule)`

Any library plugin that owns a phase of the frame must offer a
constructor that lets users relocate the schedule:

```rust
pub struct ScreenPlugin {
    schedule: InternedScheduleLabel,
}

impl Default for ScreenPlugin {
    fn default() -> Self {
        Self { schedule: PostUpdate.intern() }
    }
}

impl ScreenPlugin {
    pub fn new(schedule: impl ScheduleLabel) -> Self {
        Self { schedule: schedule.intern() }
    }
}

impl Plugin for ScreenPlugin {
    fn build(&self, app: &mut App) {
        app.add_systems(self.schedule, /* ... */);
    }
}
```

Does **not** apply to runner-style plugins (`TestRunnerPlugin`) or
app-entry plugins (`AppPlugin`) — they own the App, not a phase.

### Extension traits for registration and command verbs

When a library needs the user to register types, use a `*AppExt` trait:

```rust
pub trait RegisterScreen {
    fn register_screen<S: Screen>(&mut self) -> &mut Self;
}
impl RegisterScreen for App { /* ... */ }
```

When adding ergonomic verbs to `Commands` / `EntityCommands`, use a
`*CommandsExt` trait:

```rust
pub trait CommandsExt {
    fn assert<S: ToString>(&mut self, condition: bool, msg: S) -> bool;
    // ...
}
impl<'w, 's> CommandsExt for Commands<'w, 's> { /* ... */ }
```

Never use `Resource<Vec<Box<dyn Trait>>>` for the same purpose.
Extension traits are re-exported from the crate `prelude`.

### `PluginGroup` for multi-plugin libraries

If a library grows past 2 plugins that consumers usually want all of,
ship a `PluginGroup`:

```rust
pub struct FooPlugins;
impl PluginGroup for FooPlugins {
    fn build(self) -> PluginGroupBuilder {
        PluginGroupBuilder::start::<Self>()
            .add(FooPluginA)
            .add(FooPluginB)
            .add(FooPluginC)
    }
}
```

Individual plugins remain accessible for cherry-picking. `PluginGroup`
has been in Bevy since the early versions (`DefaultPlugins`,
`MinimalPlugins`); not a 0.19 addition.

---

## Module shape

**No mandatory skeleton.** Start with a single `lib.rs` (flat library
crate) or `mod.rs` (subsystem). We recommend splitting as soon as possible. 

When you do split, the canonical concern axes are:

| File | Contents |
|---|---|
| `data.rs` | Components, resources, states, marker types |
| `systems.rs` | System functions |
| `messages.rs` | `#[derive(Message)]` types — buffered, consumed via `MessageReader` system params |
| `events.rs` | `#[derive(Event)]` types — unbuffered, consumed via observers (`On<MyEvent>`) |
| `observers.rs` | `On<...>` observer functions, when they exceed a handful |
| `bundle.rs` | Prefab-like `impl Bundle` factories for game-state entities |
| `state.rs` | `#[derive(States)]` enums + transitions, when they merit isolation |
| `mod.rs` / `lib.rs` | `pub(super) fn plugin` + local `prelude` module |

**`bundle.rs` only appears when the crate has prefab-shaped entities**
(player controller, NPC archetypes, props). Don't create a `bundle.rs`
for trivial spawns.

---

## Messages vs events

Both exist; they are different tools. Pick the one that matches the
delivery semantics you want.

### Messages — buffered, polled

`#[derive(Message)]` types are written to a buffer and consumed by
systems holding a `MessageReader<T>` parameter. Multiple messages
between reads accumulate; readers see all messages emitted since their
last frame.

```rust
#[derive(Message, Debug)]
pub struct SwitchToScreenMsg(pub ScreenId);

fn emit(mut writer: MessageWriter<SwitchToScreenMsg>) {
    writer.write(SwitchToScreenMsg(some_id));
}

fn handle(mut reader: MessageReader<SwitchToScreenMsg>) {
    for msg in reader.read() {
        // ...
    }
}
```

Use messages when:
- Producers and consumers run in the same schedule and you want the
  consumer to see *every* message in order.
- You want to register `run_if(on_message::<T>())` so the consumer is
  skipped when there's no work.
- The work is naturally batchable ("process all click events this
  frame").
- You want to decouple producer and consumer scheduling without forcing
  a synchronous reaction.

Registration: `app.add_message::<MyMsg>()`.

### Events — unbuffered, observer-driven

`#[derive(Event)]` types fire observers synchronously when triggered.
There is no buffer; an event with no observer is dropped.

```rust
#[derive(Event, Debug)]
pub struct ScreenChanged { pub from: Option<ScreenId>, pub to: ScreenId }

fn emit(mut commands: Commands) {
    commands.trigger(ScreenChanged { from: None, to: id });
}

fn observer(trigger: On<ScreenChanged>) {
    let ev = trigger.event();
    // ...
}

// In the plugin:
app.add_observer(observer);
```

Events can be entity-targeted (`commands.entity(e).trigger(MyEvent)`),
in which case observers added with `EntityCommands::observe(...)` see
only events targeted at that entity.

Use events when:
- The reaction must happen immediately, in the same command flush.
- You want to target a specific entity's observers.
- You want bubbling (event propagates up `ChildOf` hierarchy until
  consumed).
- The reaction is fundamentally point-in-time and missing it is
  acceptable / impossible.

Registration: events do not need workspace-level registration. Observers
are registered with `app.add_observer(...)` (global) or
`commands.entity(e).observe(...)` (per-entity).

### Quick decision

| If... | Use |
|---|---|
| Multiple producers, one consumer that processes a batch per frame | Message |
| One producer, immediate reaction needed by zero or more observers | Event |
| Reaction is per-entity (e.g., "this entity was clicked") | Event (entity-targeted) |
| Reaction needs to bubble up hierarchy | Event |
| Consumer might be skipped some frames; producers shouldn't care | Message |

---

## Bundles

**Use `#[derive(Bundle)] struct` for simple amalgams of components.**
Consumers may want to name the type:

```rust
#[derive(Bundle)]
pub struct WallBundle {
    pub wall: Wall,
    pub transform: Transform,
    pub mesh: Mesh3d,
    pub material: MeshMaterial3d<StandardMaterial>,
}
```

**Use `fn foo(...) -> impl Bundle` when construction is non-trivial** —
parameters, asset handles, or `children![ ... ]` composition:

```rust
pub fn player(mesh: Handle<Mesh>, material: Handle<StandardMaterial>) -> impl Bundle {
    (
        Player,
        Transform::default(),
        Mesh3d(mesh),
        MeshMaterial3d(material),
        children![(
            CameraAnchor,
            Transform::from_xyz(0.0, 1.6, 0.0),
        )],
    )
}
```

TODO: When 0.19 is released, this is a good candidate for bsn! migration.

---

## Observers as spawn hooks

When a marker component is inserted, run setup via an observer:

```rust
fn setup_player(
    add: On<Add, Player>,
    mut commands: Commands,
    assets: Res<PlayerAssets>,
) {
    commands.entity(add.entity).insert((
        RigidBody::Kinematic,
        Collider::capsule(0.4, 0.9),
        SceneRoot(assets.model.clone()),
    ));
}

// In the plugin:
app.add_observer(setup_player);
```

Prefer this over a `Startup` system that queries-and-mutates.

---

## Prefer component lifecycle hooks over observers

Component lifecycle hooks _are_ observers. Placing them next 
to the component definition keeps context local.

Declare hooks via the `#[component(...)]` attribute on the component
definition, with each hook implemented as a function taking
`DeferredWorld` and `HookContext`:

```rust
use bevy::ecs::lifecycle::HookContext;
use bevy::ecs::world::DeferredWorld;

#[derive(Component)]
#[component(on_add = Player::on_add, on_remove = Player::on_remove)]
pub struct Player {
    pub stats: PlayerStats,
}

impl Player {
    fn on_add(mut world: DeferredWorld, ctx: HookContext) {
        // Insert collateral components, register input maps, etc.
        world.commands().entity(ctx.entity).insert((
            RigidBody::Kinematic,
            Collider::capsule(0.4, 0.9),
        ));
    }

    fn on_remove(mut world: DeferredWorld, ctx: HookContext) {
        // Tear down side-effects keyed off this entity.
        if let Some(input) = world.get_resource_mut::<InputMaps>() {
            input.unregister(ctx.entity);
        }
    }
}
```

Available hooks: `on_add`, `on_insert`, `on_replace`, `on_remove`.

The distinction vs `app.add_observer(...)`:

- **Lifecycle hooks** are declared with the component, run
  unconditionally for every insert/remove of that component, and live
  next to the type they react to. Use these when the reaction is
  intrinsic to the component's existence.
- **Standalone observers** (`On<Add, T>`, `On<MyEvent>`) are
  registered with the plugin, may be added/removed independently, and
  can target arbitrary events. Use these for cross-cutting reactions or
  reactions that depend on plugin configuration.

If the reaction logically belongs to the component itself, use a
lifecycle hook. If the reaction is owned by some other plugin or
subsystem, use an observer there.

---

## `Startup` is for long-lived singletons only

Use `Startup` (and `PostStartup`/`PreStartup`) for app-singleton setup
that has no marker to observe and that has lifetime equal to the app's:
top-level cameras, root UI containers, persistent global resources.

For everything else, prefer lazy initialization via observers or
on-demand spawn from systems gated on a state/condition.

---

## Required components

Use `#[require(Transform, Visibility)]` (or `#[require(A = expr)]`) on
marker components instead of bundle structs:

```rust
#[derive(Component)]
#[require(Transform, Visibility, RigidBody)]
pub struct Player;
```

Crate-specific derives (e.g., `bevy_trenchbroom`'s
`#[point_class(base(Transform, Visibility), ...)]`) often expand to
`#[require]` under the hood. Both are acceptable.

---

## Imports and prelude

Every crate exports a `pub mod prelude { ... }` with the types
consumers reach for. Submodules use `use crate::prelude::*;`. External
consumers use `use <crate>::prelude::*;`.

Granular imports only to resolve ambiguity (e.g., name collisions with
`bevy::prelude`). This is project policy and intentionally diverges
from Bevy upstream's "no glob imports" contributor rule. See
[`workspace-conventions.md`](workspace-conventions.md) for rationale.
