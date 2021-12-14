
TWOPENCE_TESTDIR	= /usr/lib/twopence

all: ;

install:
	cp -av tests/* $(DESTDIR)$(TWOPENCE_TESTDIR)
