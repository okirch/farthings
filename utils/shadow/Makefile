BINDIR	= /usr/bin

CCOPT	= -O2
CFLAGS	= -Wall $(CCOPT)
APPS	= verify_password

all: $(APPS)

install: $(APPS)
	install -m 755 -d $(DESTDIR)$(BINDIR)
	install -m 555 $(APPS) $(DESTDIR)$(BINDIR)

tags: .FORCE
	ctags $(addprefix ,$(ALLSRCS))

.FORCE: ;

clean:
	rm -rf obj $(APPS)

verify_password: verify_password.c
	$(CC) $(CFLAGS) -o $@ verify_password.c -lcrypt
