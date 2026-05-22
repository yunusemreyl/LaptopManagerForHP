# Troubleshooting

## `omen` CLI fails with `ModuleNotFoundError: No module named 'pydbus'`

### Symptom

```bash
$ omen fan auto
Traceback (most recent call last):
  File "/usr/bin/omen", line 4, in <module>
    from pydbus import SystemBus
ModuleNotFoundError: No module named 'pydbus'
```

### Root Cause

Your `PATH` may prioritize a non-system Python interpreter — commonly a Conda or virtual-environment installation — that does not share packages with the system Python. The project uses `#!/usr/bin/env python3` in its installed scripts, which picks whichever `python3` is first in `PATH` rather than the system one where `python3-pydbus` was installed by the package manager.

### Fix

Update the installed scripts to use the system Python directly:

```bash
sudo sed -i '1s|#!/usr/bin/env python3|#!/usr/bin/python3|' /usr/bin/omen
sudo sed -i 's|exec python3 |exec /usr/bin/python3 |' /usr/bin/hp-manager
```

### Verification

```bash
head -n 1 /usr/bin/omen
# Expected: #!/usr/bin/python3

omen fan auto
# Expected: Fan mode set to auto: OK
```

### Permanent Fix

If you reinstall or update via `setup.sh`, the scripts may be overwritten and revert to `#!/usr/bin/env python3`. Re-apply the fix after each update, or modify `src/omen-cli.py` and the GUI launcher in the source tree before running `setup.sh`.
