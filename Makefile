
TWOPENCE_TESTDIR	= /usr/lib/twopence
TWOPENCE_SUITESDIR	= $(TWOPENCE_TESTDIR)/suites
TWOPENCE_MATRIXDIR	= $(TWOPENCE_TESTDIR)/matrices

all install clean::
	@for dir in utils/*; do \
		make -C $$dir $@; \
	done

install install-tests::
	twopence install-testcase tests/*

install install-suites::
	twopence install-testsuite suites/*

install install-matrices::
	twopence install-testmatrix matrices/*
