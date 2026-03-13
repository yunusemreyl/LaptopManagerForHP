
# Module names — both built together
obj-m += hp-wmi.o
obj-m += hp-rgb-lighting.o

# Kernel build directory
KDIR := /lib/modules/$(shell uname -r)/build

PKGNAME := $(shell grep -oP 'PACKAGE_NAME="\K[^"]+' dkms.conf)
VERSION := $(shell grep -oP 'PACKAGE_VERSION="\K[^"]+' dkms.conf)

# Current directory
PWD := $(shell pwd)

# Detect if the running kernel was compiled with Clang
LLVM_DETECTED := $(shell grep -iq clang /proc/version && echo 1 || echo 0)
LLVM ?= $(LLVM_DETECTED)

# Default target
all:
ifeq ($(LLVM),1)
	$(MAKE) LLVM=1 -C $(KDIR) M=$(PWD) modules
else
	$(MAKE) -C $(KDIR) M=$(PWD) modules
endif

# Clean target
clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
	rm -rf *.pkg.tar.zst

install: all
	$(MAKE) -C $(KDIR) M=$(PWD) modules_install
	depmod -a

install-dkms:
	dkms add .
	dkms build -m $(PKGNAME) -v $(VERSION)
	dkms install -m $(PKGNAME) -v $(VERSION)

install-arch:
	makepkg -si

uninstall:
	rm -f /lib/modules/$(shell uname -r)/extra/hp-wmi.ko
	rm -f /lib/modules/$(shell uname -r)/extra/hp-rgb-lighting.ko
	depmod -a

uninstall-dkms:
	dkms remove -m $(PKGNAME) -v $(VERSION) --all
	rm -rf /usr/src/$(PKGNAME)-$(VERSION)

.PHONY: all clean install uninstall install-dkms uninstall-dkms install-arch