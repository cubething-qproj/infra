<div align="center">
    <img height=300 src="./docs/qproj.png" alt="illustration of a quail next to text, 'qproj' " title="qproj logo"></img>
</div>

Shared infrastructure for the _qproj_ family of crates — scripts, Cargo
workspace config, Nix flake, CI, and dev tooling.

## Crates

| Crate | Description |
|-------|-------------|
| [quell](https://github.com/cubething-qproj/quell) | Game binary + assets |
| [q_screens](https://github.com/cubething-qproj/q_screens) | Screens extension for Bevy |
| [q_term](https://github.com/cubething-qproj/q_term) | Bevy terminal emulator widget |
| [q_test_harness](https://github.com/cubething-qproj/q_test_harness) | Simple test harness for Bevy applications |

## Requirements

- Unix-based OS
- [direnv](https://direnv.net/)
- [nix](https://nixos.org/download/)
- [just](https://github.com/casey/just)

## Getting Started

```sh
# Will sync to ~/repos/cubething-qproj.
# Set BASE_DIR to change the base directory.
uvx --refresh --from "git+https://github.com/cubething-qproj/infra.git@main#subdirectory=scripts" qproj-scripts sync
```

## Compatibility

| branch/tag | bevy |
| ---------- | ---- |
| main       | 0.18 |

## About the bird
> _The California quail is a highly sociable bird that often gathers in small flocks known as "coveys". One of their daily communal activities is a dust bath. A group of quail will select an area where the ground has been newly turned or is soft, and using their underbellies, will burrow downward into the soil some one to two inches. They then wriggle about in the indentations they have created, flapping their wings and ruffling their feathers, causing dust to rise in the air. They seem to prefer sunny places in which to create these dust baths. An ornithologist is able to detect the presence of quail in an area by spotting the circular indentations left behind in the soft dirt, some 7–15 cm (2.8–5.9 in) in diameter._ ([wikipedia](https://en.wikipedia.org/wiki/California_quail))

## License

Licensed under either of [Apache License, Version 2.0](LICENSE-APACHE.txt) or
[MIT License](LICENSE-MIT.txt) at your option.
