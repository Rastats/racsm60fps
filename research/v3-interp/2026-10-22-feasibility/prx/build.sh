#!/bin/sh
# Build InterpRender inside the pinned pspdev image (run from the host):
#   docker run --rm -v <this folder>:/src -w /src pspdev/pspdev:v20261001 sh build.sh
# Output: build/InterpRender/{interp_render.prx,plugin.ini}, build/symbols.txt, build/sizes.txt
set -e
SDK=$(psp-config --pspsdk-path)
PREFIX=$(psp-config --psp-prefix)
mkdir -p build/InterpRender
FLAGS="-O2 -G0 -std=c11 -Wall -Wextra -Werror -fno-strict-aliasing -fno-math-errno -D_PSP_FW_VERSION=660 -I$PREFIX/include -I$SDK/include"
psp-gcc $FLAGS -c interp_render.c -o build/interp_render.o
psp-gcc $FLAGS -L$PREFIX/lib -L$SDK/lib -specs=$SDK/lib/prxspecs -Wl,-q,-T$SDK/lib/linkfile.prx \
    -Wl,-zmax-page-size=128 -nostdlib -nostartfiles build/interp_render.o $SDK/lib/prxexports.o \
    -lpspmodinfo -lgcc -o build/interp_render.elf
psp-nm build/interp_render.elf | grep -E ' (ir_cfg|ir_stat|ir_pump|ir_render)$' > build/symbols.txt
psp-size -A build/interp_render.elf > build/sizes.txt
psp-prxgen build/interp_render.elf build/InterpRender/interp_render.prx
cp plugin.ini build/InterpRender/plugin.ini
sha256sum build/InterpRender/interp_render.prx interp_render.c
cat build/symbols.txt
grep -E '^\.(text|data|bss|rodata)' build/sizes.txt
