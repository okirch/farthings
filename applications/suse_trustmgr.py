##################################################################
#
# Define a class that installs CA certificates and makes them
# trusted
#
# Copyright (C) 2022, Olaf Kirch <okir@suse.com>
#
##################################################################

import susetest
import twopence
import os

class SUSETrustManager(susetest.Application):
	id = "suse_trustmgr"
	service_name = None

	def addTrustedCertificate(self, name, data):
		twopence.info(f"About to install trusted cert {name}")
		node = self.target

		res = node.requireDirectory("trust-certificates")
		if not res:
			node.logFailure(f"Could not determine trust-certificates directory")
			return 

		path = os.path.join(res.path, name)
		print(f"upload to {path}")
		st = node.sendbuffer(path, data, quiet = True, user = "root")
		if not st:
			node.logFailure(f"Failed to upload certificate to {path}: {st.message}")
			return False

		res = node.requireExecutable("update-certificate-trust")
		if not res:
			node.logFailure(f"Could not determine update-certificate-trust executable")
			return 

		st = res.run()
		if not st:
			node.logFailure(f"Failed to update certificates: {st.message}")
			return False

		node.logInfo(f"Installed certificate {name} as trusted")
		return True

