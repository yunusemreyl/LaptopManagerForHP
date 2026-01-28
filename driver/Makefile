obj-m += hp-wmi.o

all:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules

clean:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean

install:
	sudo cp hp-wmi.ko /lib/modules/$(shell uname -r)/kernel/drivers/platform/x86/
	sudo depmod -a
	sudo modprobe hp-wmi
