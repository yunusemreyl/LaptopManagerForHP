savedcmd_hp-omen-core.mod := printf '%s\n'   hp-omen-core.o | awk '!x[$$0]++ { print("./"$$0) }' > hp-omen-core.mod
