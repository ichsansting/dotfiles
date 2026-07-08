# dotfiles

Personal developer environment managed with [Nix flakes](https://nixos.wiki/wiki/Flakes) and [home-manager](https://github.com/nix-community/home-manager) (standalone, no NixOS or nix-darwin required), driven by a single-screen TUI.

Works on **Linux** and **macOS**.

---

## What's included

| Module | Components (individually toggleable) |
|---|---|
| `terminal` | fish · starship · atuin · zoxide · zellij |
| `vcs` | git (SSH commit signing) · delta · gh · ssh |
| `editor` | helix · language-servers |
| `devenv` | mise · direnv · ai (claude-code + .claude skills) |
| `utils` | search (fzf/rg/fd) · files (eza/yazi/dust/duf) · view (bat/jq) · monitor (btop) · nix-tools (nvd/nix-tree/comma) |
| `env` | XDG directories and editor/pager environment variables |
| `work` | aws-tools · granted · env (off by default) |
| `claude-oauth` | encrypted Claude Code credentials (on in the `personal` preset) |

Every module is a parent with toggleable children — enable `terminal` but turn off just `atuin`, per machine, without touching Nix.

Secrets are encrypted with [sops](https://github.com/getsops/sops) + [age](https://age-encryption.org/) and committed to the repo. On activation, home-manager decrypts each tracked secret to its mirrored `$HOME` path — no systemd required, works in containers.

---

## Bootstrap

The only dependency is **Nix** — the flake provides everything else (python + textual for the TUI, sops, age, openssh, home-manager; pytest/ruff in the devShell).

With Nix installed:

```bash
nix run nixpkgs#git -- clone https://github.com/ichsansting/dotfiles.git ~/dotfiles
cd ~/dotfiles
nix run . --impure
```

On a fresh machine without Nix, `bash bootstrap.sh` installs it first (uses curl once), then launches the TUI.

---

## The TUI

One lazygit-style screen, fully keyboard-driven:

```
 dotfiles ~/dotfiles · preset: work +1 override · age key ✓
┌─1 ─ modules─────────────┐┌─0 ─ preview──────────────────────┐
│ ▼ ■ terminal            ││                                  │
│    ■ fish               ││   preview · diff · live log      │
│    □ atuin *            ││   of whatever you're doing       │
│ ▶ ■ vcs                 ││                                  │
├─2 ─ files───────────────┤│                                  │
│ vcs  S .ssh/id_ed…    ✓ ││                                  │
│ work P .aws/config    ! ││                                  │
└─────────────────────────┘└──────────────────────────────────┘
 space toggle · d diff · s sync ↑ · D deploy ↓ · a apply · ? help
```

- **`1` Modules** — `space` toggles a module or one of its components. Changes save immediately as *local overrides* on top of the active preset (`*` marks overridden entries, `x` reverts one to the preset).
- **`2` Files** — every tracked file, plain (`P`) and secret (`S`), in one list: `enter` preview, `d` diff, `s` sync `$HOME → repo` (re-encrypts secrets), `D` deploy `repo → $HOME`, `n` track a new file, `x` untrack, `e` edit.
- **`0` Main pane** — shows previews, diffs, and the live `home-manager switch` log.
- **Global** — `a` apply, `p` switch preset, `b` backup age key, `G` garbage-collect, `U` uninstall, `?` full key reference.

---

## Presets and overrides

Machine configuration = **preset** (committed) + **local overrides** (never committed).

- Presets live in `presets/*.json` (`default`, `personal`, `work`) and select modules/children plus settings like git identity. `default.json` is the base; every other preset holds only its **diff** from the default and is layered over it on load — shared settings (like git identity) live once, in `default.json`.
- The active preset and your overrides are stored per-machine in `~/.local/state/dotfiles/profile.json` (gitignored). Toggling in the TUI writes only the *delta* from the preset; toggling back to the preset value removes the override.

```json
{ "preset": "work", "overrides": { "modules": { "terminal": { "children": { "atuin": false } } } } }
```

---

## Tracked files (plain + secret)

Each module tracks the files it owns in `modules/<name>/files.json`; the content lives under `modules/<name>/files/`, mirroring `$HOME`:

```
modules/vcs/files/.ssh/id_ed25519.sops.yaml   →  ~/.ssh/id_ed25519        (secret)
modules/work/files/.aws/config                →  ~/.aws/config            (plain)
```

The only difference between the two modes is encryption at rest:

- **plain** — committed verbatim.
- **secret** — sops-encrypted with your age key; decrypted on activation.

Track a new file with `n` in the TUI (pick the file, module, and mode), then commit the result. Deploys never clobber local changes silently — diff/sync first, or confirm the overwrite when deploying from the TUI.

### Composed files (fragments)

One `$HOME` file can be assembled from blocks contributed by several modules: mark each entry with `"fragment": true` (and an optional `"order"`, default 100) in the contributing modules' `files.json`. At apply time the enabled fragments are concatenated — sorted by `order`, then module name, with a blank line between blocks — into the single target file:

```json
// modules/devenv/files.json — base block
{ "path": ".claude/CLAUDE.md", "mode": "plain", "child": "ai", "fragment": true, "order": 10 }
// modules/work/files.json — appended only when work is enabled
{ "path": ".claude/CLAUDE.md", "mode": "plain", "fragment": true, "order": 50 }
```

Each module stores its own block under its `files/` dir (a fragment may be `secret` — it is decrypted before composing; if the age key is missing the whole target is skipped rather than deployed half-built). A path is either whole-file (one owner) or all-fragments — mixing the two styles is a config error caught before anything deploys. Fragments show as `F` in the TUI files panel; sync `$HOME → repo` is disabled for them — edit the module's fragment (`e`) and apply instead. Disabling a contributor rewrites the composed file without it on the next apply; when the last one goes, the file is pruned.

For formats with an include mechanism (like fish's `conf.d/`), tracking a separate per-module file is simpler than composing one — fragments are for single-file formats like `CLAUDE.md`.

Deployment is declarative: every deployed file is recorded (path + content hash) in `~/.local/state/dotfiles/deployed.json`, and the next `home-manager switch` prunes anything that fell out of the desired set — a disabled module or child, an untracked file, a deleted module. Files you edited locally are never pruned automatically; they show up as **orphans** in the TUI's files panel, where you resolve them — track the file into a module (`n`) or delete it (`x`) behind a confirmation dialog.

---

## Age key

On first run the TUI offers to **restore** your key from the committed, passphrase-protected `identity.age`, or **generate** a fresh one (which also updates `.sops.yaml`). Back it up any time with `b` and commit `identity.age`.

---

## Adding a module

1. `mkdir modules/<name>` with a `default.nix` and a `module.json` (`description` + `children`). Both Nix and the TUI discover modules from `module.json` — there is no list to update anywhere else. (Or press `N` in the TUI, which scaffolds this and offers to enable the module in the active preset or on this machine only.)
2. Enable it where it should run: in `presets/default.json` for every machine, or as a diff entry in a specific preset — presets are layered over the default.
3. Follow the existing pattern: options come from `lib/module-options.nix`, each child is a `lib.mkIf (on "<child>")` block.

Modules with tracked files also get a `files.json` + `files/`; deployment is wired automatically by `lib/files-activation.nix`.

---

## Updating

```bash
cd ~/dotfiles
git pull
nix flake update          # optional: update nixpkgs + home-manager
nix run . --impure        # then press `a`
```

Or directly: `home-manager switch --flake ~/dotfiles#default --impure`.

---

## Development

```bash
nix develop               # python + textual + pytest, ruff, sops, age, nixfmt
pytest                    # core + TUI (headless Pilot) tests
ruff check pkg tests
```

---

## Repository structure

```
dotfiles/
├── flake.nix                  # inputs, tui package/app, devShell, homeConfigurations."default"
├── home.nix                   # thin root: auto-discovers modules, feeds the resolved profile
├── bootstrap.sh               # install Nix → launch the TUI
├── identity.age               # passphrase-protected age private key (safe to commit)
├── .sops.yaml                 # age public key + encryption path rule
├── presets/                   # committed machine presets (default, personal, work)
├── lib/
│   ├── modules.nix            # module auto-discovery (single source of truth)
│   ├── module-options.nix     # module.json → dotfiles.<mod>.<child>.enable options
│   ├── profile.nix            # preset + overrides resolution at eval time
│   └── files-activation.nix   # deploy + prune activation (declarative undeploy)
├── modules/<name>/
│   ├── default.nix            # options from module.json; one mkIf block per child
│   ├── module.json            # description + children (read by Nix AND the TUI)
│   ├── files.json             # tracked-files manifest (path + plain|secret)
│   └── files/                 # mirrored $HOME content (secrets as *.sops.yaml)
├── pkg/dotfiles/
│   ├── core/                  # stdlib-only logic (profiles, manifests, sops, age)
│   ├── tui/                   # Textual dashboard (screens/, widgets/, styles.tcss)
│   └── activate.py            # CLI used by home-manager activation hooks
└── tests/                     # pytest: core units + headless TUI smoke tests
```
