/*
 * RPC Test suite
 *
 * Copyright (C) 2011, Olaf Kirch <okir@suse.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 *
 *
 * -T <nettype>
 *	Can be one of the common nettypes (like netpath, visible, circuit_n, circuit_v,
 *	datagram_n, datagram_v, tcp, and udp).
 *	Specifying -T with an empty string causes it to call svc_reg with a NULL nettype.
 *
 */
#include "rpctest.h"
#include <getopt.h>
#include <unistd.h>

int
main(int argc, char **argv)
{
	const char *opt_nettype[16];
	int opt_foreground = 0;
	int opt_oldstyle = 0;
	char *opt_pidfile = "/var/run/squared.pid";
	int opt_kill = 0;
	unsigned int num_nettypes = 0;
	int c;

	while ((c = getopt(argc, argv, "fKp:oT:")) != EOF) {
		switch (c) {
		case 'f':
			opt_foreground = 1;
			break;

		case 'K':
			opt_kill = 1;
			break;

		case 'p':
			opt_pidfile = optarg;
			break;

		case 'o':
			opt_oldstyle = 1;
			break;

		case 'T':
			if (optarg && *optarg == '\0')
				optarg = NULL;
			opt_nettype[num_nettypes++] = optarg;
			break;

		default:
		usage:
			fprintf(stderr,
				"Usage:\n"
				"rpc.squared [-h hostname] [-T nettype]\n");
			return 1;
		}
	}

	if (optind != argc)
		goto usage;

	if (opt_kill) {
		if (rpctest_pidfile_kill(opt_pidfile) <= 0) {
			fprintf(stderr, "Failed to send SIGTERM to rpc.squared - maybe the process is gone?\n");
			return 1;
		}
		return 0;
	}

	if (opt_pidfile) {
		if (rpctest_pidfile_check(opt_pidfile)) {
			fprintf(stderr, "It appears there's another rpc.squared running\n");
			return 1;
		}

		/* We write a pidfile here, even for the daemon case, so that we can
		 * catch errors resulting from lack of permissions etc. */
		if (rpctest_pidfile_write(opt_pidfile, getpid()) < 0) {
			fprintf(stderr, "Failed to write %s: %m\n", opt_pidfile);
			return 1;
		}
	}


	if (num_nettypes) {
		unsigned int i = 0;

		for (i = 0; i < num_nettypes; ++i) {
			const char *nettype = opt_nettype[i];

			if (!rpctest_register_service_nettype(SQUARE_PROG, SQUARE_VERS, square_prog_1, nettype))
				return 1;
		}
	} else
	if (opt_oldstyle) {
		rpctest_run_oldstyle(SQUARE_PROG, SQUARE_VERS, square_prog_1);
	} else {
		rpctest_run_newstyle(SQUARE_PROG, SQUARE_VERS, square_prog_1);
	}

	if (!opt_foreground) {
		if (daemon(0, 0) < 0) {
			fprintf(stderr, "Unable to background process\n");
			return 1;
		}

		if (opt_pidfile && rpctest_pidfile_write(opt_pidfile, getpid()) < 0)
			return 22;
	}

	svc_run();
	exit(1);
}
