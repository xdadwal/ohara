# Compose definitions

Each standalone project uses `PROJECT.yaml`, paired with public pins in
`../versions/PROJECT.env`. `stack.yaml` is the eleven-app main stack. The two
files under `overrides/` are conditionally included main-stack overlays.

Use the existing scripts, which pass the repository root as project directory;
do not run Compose from this folder or load private `.env` directly.
See [layout, migration, verification and rollback](../docs/deployment-layout.md).
