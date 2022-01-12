
TWOPENCE_TESTDIR	= /usr/lib/twopence

all install clean::
	@for dir in utils/*; do \
		make -C $$dir $@; \
	done

install install-tests::
	@for dir in tests/*; do \
		test -d $$dir || continue; \
		tn="$${dir#*/}"; \
		dstdir=$(DESTDIR)$(TWOPENCE_TESTDIR)/$$tn; \
		echo "Installing $$dir -> $$dstdir"; \
		mkdir -p $$dstdir; \
		cp $$dir/* $$dstdir; \
	done
