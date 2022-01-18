/*
 * verify_password
 *
 * Simple utility for checking a user password using crypt(3)
 *
 * Copyright (C) 2022, Olaf Kirch <okir@suse.de>
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
 */
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <shadow.h>
#include <string.h>
#include <unistd.h>
#include <crypt.h>
#include <getopt.h>

static const char *		opt_verify_algorithm = NULL;

static void
fatal(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
	exit(1);
}

static const char *
get_crypt_algorithm(const char *crypted_password)
{
	if (!crypted_password)
		return NULL;

	if (crypted_password[0] != '$')
		return "des";

	if (crypted_password[2] != '$')
		return NULL;

	switch (crypted_password[1]) {
	case '1':
		return "md5";
	case '5':
		return "sha256";
	case '6':
		return "sha512";
	}

	return NULL;
}

static void
verify_password(const char *username, const char *password)
{
	const char *shadow_passwd;
	const char *shadow_algorithm;
	struct spwd *spwd;
	char *encrypted;

	spwd = getspnam(username);
	if (spwd == NULL)
		fatal("Unknown user %s\n", username);

	shadow_algorithm = get_crypt_algorithm(spwd->sp_pwdp);
	if (shadow_algorithm == NULL)
		fatal("Unable to guess crypt algorithm for password of %s\n", username);

	if (opt_verify_algorithm && strcasecmp(opt_verify_algorithm, shadow_algorithm))
		fatal("User password is hashed using %s (expected %s)\n", shadow_algorithm, opt_verify_algorithm);

	printf("User's password is hashed using %s\n", shadow_algorithm);

	if (password == NULL) {
		password = getpass("Please enter password: ");
		if (password == NULL)
			fatal("Unable to get password");
	}

	shadow_passwd = spwd->sp_pwdp;
	encrypted = crypt(password, spwd->sp_pwdp);
	if (encrypted == NULL)
		fatal("Failed to encrypt password: %m\n");

	if (strcmp(shadow_passwd, encrypted))
		fatal("Passwords do not match\n");

	endspent();
}

static struct option	options[] = {
	{ "algorithm",		required_argument,	NULL,	'A' },
	{ NULL, }
};

static void
usage(int exitval)
{
	fprintf(stderr, "Usage: verify_passwd [--algorithm HASHALGO] USERNAME PASSWORD\n");
	exit(exitval);
}

int
main(int argc, char **argv)
{
	int c;

	while ((c = getopt_long(argc, argv, "A:", options, NULL)) >= 0) {
		switch (c) {
		case 'A':
			opt_verify_algorithm = optarg;
			break;

		default:
			usage(1);
		}
	}

	if (argc - optind == 1) {
		verify_password(argv[optind], NULL);
	} else if (argc - optind == 2) {
		verify_password(argv[optind], argv[optind + 1]);
	} else {
		usage(1);
	}

	printf("Password verified OK.\n");
	return 0;
}
