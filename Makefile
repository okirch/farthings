
TWOPENCE_TESTDIR	= /usr/lib/twopence

all: ;

install:
	@for dir in tests/*; do \
		test -d $$dir || continue; \
		tn="$${dir#*/}"; \
		dstdir=$(DESTDIR)$(TWOPENCE_TESTDIR)/$$tn; \
		echo "Installing $$dir -> $$dstdir"; \
		mkdir -p $$dstdir; \
		cp $$dir/* $$dstdir; \
	done
