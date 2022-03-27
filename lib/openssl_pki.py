##################################################################
#
# Define a class that implements X.509 certificate and key
# management, based on openssl
#
# Copyright (C) 2022, Olaf Kirch <okir@suse.com>
#
##################################################################

import subprocess
import twopence
import tempfile
import os

DEFAULT_CONFIG = '''
[ req ]
#default_bits		= 2048
#default_md		= sha256
#default_keyfile	= privkey.pem
distinguished_name	= req_distinguished_name
attributes		= req_attributes

[ req_distinguished_name ]
countryName		= Country Name (2 letter code)
countryName_min		= 2
countryName_max		= 2
stateOrProvinceName	= State or Province Name (full name)
localityName		= Locality Name (eg, city)
organizationName	= Organization Name (eg, company)
organizationalUnitName  = Organizational Unit Name (eg, section)
commonName		= Common Name (eg, fully qualified host name)
commonName_max		= 64
emailAddress		= Email Address
emailAddress_max	= 64

[ req_attributes ]
challengePassword	= A challenge password
challengePassword_min   = 4
challengePassword_max   = 20
'''

class Config:
	def __init__(self):
		self.extensions = []
		self.extensionLines = []

		self.file = None

	@property
	def path(self):
		if self.file is None:
			self.file = tempfile.NamedTemporaryFile(mode = "w", prefix = "pki-", suffix = ".conf")
			self.file.write(DEFAULT_CONFIG)
			for line in self.extensionLines:
				print(line, file = self.file)
			self.file.flush()
		return self.file.name

	@property
	def extensionPath(self):
		if self.file is None:
			self.file = tempfile.NamedTemporaryFile(mode = "w", prefix = "pki-", suffix = ".conf")
			for line in self.extensionLines:
				print(line, file = self.file)
			self.file.flush()
		return self.file.name

	def applyRequestParameters(self, req):
		extSection = []
		if req.altSubjectNames:
			extSection.append("subjectAltName          =" + ",".join(req.altSubjectNames))
		if req.extendedKeyUsage:
			extSection.append("extendedKeyUsage        = " + req.extendedKeyUsage)

		self.addExtensionSection("EXT", extSection)

		if req.CA:
			self.addExtensionSection("CA", [
						"basicConstraints = CA:TRUE",
					])

	def addExtensionSection(self, name, lines):
		if not lines:
			return

		self.extensions.append(name)

		self.extensionLines.append(f"[{name}]")
		self.extensionLines += lines

class CertificateParameters:
	def __init__(self, subject, extendedKeyUsage = None, CA = False):
		self.subject = subject
		self.altSubjectNames = []
		self.extendedKeyUsage = extendedKeyUsage
		self.validity = 365
		self.CA = CA

	def addAltSubjectName(self, type, name):
		type = type.upper()
		if type not in ('DNS', ):
			raise ValueError(f"Bad type {type} for subjectAltName {name}")
		self.altSubjectNames.append(f"{type}:{name}")

	def generateConfig(self):
		config = Config()
		config.applyRequestParameters(self)
		return config

class FileBackedThing:
	file_suffix = None

	def __init__(self, path):
		assert(self.file_suffix)

		self.file = None
		if path is None:
			self.file = tempfile.NamedTemporaryFile(mode = "w", suffix = self.file_suffix)
			path = self.file.name
		self.path = path

class Key(FileBackedThing):
	file_suffix = ".key"

	def __init__(self, path, passphrase = None):
		super().__init__(path)
		self.passphrase = passphrase

class CSR(FileBackedThing):
	file_suffix = ".csr"

	def __init__(self, path = None, params = None, privateKey = None):
		super().__init__(path)
		self.privateKey = privateKey
		self.params = params
		return

		self.file = None
		if path is None:
			self.file = tempfile.NamedTemporaryFile(mode = "w", suffix = ".csr")
			path = self.file.name
		self.path = path

class Certificate:
	def __init__(self, path = None, privateKey = None):
		self.privateKey = privateKey
		self.file = None
		if path is None:
			self.file = tempfile.NamedTemporaryFile(mode = "w", suffix = ".cert")
			path = self.file.name
		self.path = path

	@property
	def blob(self):
		with open(self.path, "rb") as f:
			return f.read()

class CA:
	def __init__(self, pki, directory, cn):
		self.pki = pki
		self.directory = directory
		self.cn = cn
		self.key = None
		self.cert = None

		if not os.path.isdir(directory):
			os.makedirs(directory, 0o755)

	def getPathFor(self, *args):
		path = os.path.join(self.directory, *args)
		if not os.path.isdir(path):
			os.makedirs(path, 0o755)
		return path

class Server:
	def __init__(self, hostname):
		self.hostname = hostname
		self.key = None
		self.cert = None

class PKI:
	def __init__(self, workspace = None, timeout = 10):
		self.workspace = workspace
		self.path = "openssl"
		self.timeout = timeout
		self.command = None
		self.target = None

	# If we're configuring a containerized application, we will be using
	# a local config directory that is mounted into the container at
	# runtime. In this case, we do not need openssl in the container,
	# we just need it on the host.
	#
	# So, if you want to do the PKI stuff inside the SUT, call configureTarget.
	# Otherwise, don't.
	def configureTarget(self, target):
		# self.command = target.requireExecutable("openssl")
		self.target = target

	def run(self, *args):
		if self.command is not None:
			st = self.command.run(*args, timeout = self.timeout)
			return bool(st)

		twopence.debug(f"  About to run {' '.join(args)}")
		cmd = subprocess.Popen([self.path] + list(args))
		cmd.communicate(timeout = self.timeout)
		return cmd.returncode == 0

	def readCertificate(self, path):
		if self.target is not None:
			return self.target.recvbuffer(path)

		with open(path, "rb") as f:
			return f.read()

	def dump(self, thing):
		if isinstance(thing, Certificate):
			self.run("x509", "-text", "-noout", "-in", thing.path)
		elif isinstance(thing, CSR):
			self.run("req", "-text", "-noout", "-in", thing.path)
		else:
			raise ValueError(f"PKI.dump: unable to handle {thing.__class__.__name__} objects")

	def removePassphrase(self, keyIn, outKeyPath):
		twopence.info(f"::: Removing passphrase from key, storing result in {outKeyPath}")
		args = ["rsa"]

		if keyIn.passphrase:
			args += ["-passin", f"pass:{keyIn.passphrase}"]

		args += ["-in", keyIn.path, "-out", outKeyPath]
		if not self.run(*args):
			twopence.error(f"Failed to remove passphrase from key {keyIn.path}")
			return None

		return Key(outKeyPath)

	def generatePrivateKey(self, keyPath = None, passphrase = None, bits = 2048):
		key = Key(path = keyPath, passphrase = passphrase)

		args = ["genrsa"]
		if passphrase:
			args += ["-aes256", "-passout", f"pass:{key.passphrase}"]
		args += ["-out", key.path, str(bits)]

		if not self.run(*args):
			twopence.error(f"Failed to generate RSA key {key.path}")
			return None

		return key

	def parametersForSSLServer(self, hostname, validity = 365):
		return CertificateParameters(f"/CN={hostname}", extendedKeyUsage = "serverAuth")

	def parametersForCA(self, caName, validity = 365):
		return CertificateParameters(f"/CN={caName}", extendedKeyUsage = "critical, keyCertSign", CA = True)

	def runReq(self, args, privateKey, certificateParams, outPath):
		args = ["req"] + args + [
			"-subj", certificateParams.subject,
			"-key", privateKey.path]
		if certificateParams.validity and "-x509" in args:
			args += ["-days", str(certificateParams.validity)]
		if privateKey.passphrase:
			args += ["-passin", f"pass:{privateKey.passphrase}"]
		args += ["-out", outPath]

		config = certificateParams.generateConfig()

		if False:
			print("--- CONFIG FILE ---")
			with open(config.path) as f:
				print(f.read())
			print("--- END CONFIG FILE ---")

		args += ["-config", config.path]
		for ext in config.extensions:
			args += ["-extensions", ext]

		return self.run(*args)

	def createSelfSignedCert(self, certificateParams, privateKey, outPath = None):
		twopence.info(f"::: Creating Self-signed Certificate {certificateParams.subject}")
		cert = Certificate(path = outPath, privateKey = privateKey)

		if not self.runReq(["-new", "-x509", "-sha256"], privateKey, certificateParams, cert.path):
			twopence.error(f"Failed to create certificate {cert.path}")
			return None

		return cert

	def createCSR(self, certificateParams, privateKey, outPath = None):
		twopence.info(f"::: Creating Certificate Signing Request for {certificateParams.subject}")

		req = CSR(path = outPath, params = certificateParams, privateKey = privateKey)

		if not self.runReq(["-new", "-sha256"], privateKey, certificateParams, req.path):
			twopence.error(f"Failed to create certificate request {req.path}")
			return None

		return req
		args = ["req", "-new", "-in", cert.path,
			"-signkey", caKey.path, 
			"-passin", f"pass:{caKey.passphrase}",
			"-out", outPath]
		if not self.run(*args):
			return None

		return req

	def signCSR(self, caCert, req, outPath):
		twopence.info(f"::: Signing Certificate {req.params.subject}")

		cert = Certificate(path = outPath, privateKey = req.privateKey)

		certificateParams = req.params

		args = ["x509", "-req", "-sha256",
			"-CA", caCert.path,
			"-CAkey", caCert.privateKey.path,
			"-CAcreateserial",
			"-passin", f"pass:{caCert.privateKey.passphrase}"]
		if certificateParams.validity:
			args += ["-days", str(certificateParams.validity)]

		config = certificateParams.generateConfig()
		if config.extensions:
			args += ["-extfile", config.extensionPath]
			for ext in config.extensions:
				args += ["-extensions", ext]

		args += [
			"-in", req.path,
			"-out", cert.path
			]

		if not self.run(*args):
			twopence.error(f"Failed to sign certificate request {req.path}")
			return None

		return cert

	def createCA(self, cn, directory = None, passphrase = None):
		twopence.info(f"::: Creating Certificate Authority {cn}")

		if directory is None:
			assert(self.workspace)
			directory = os.path.join(self.workspace, cn)

		ca = CA(self, directory, cn)

		path = os.path.join(directory, "ca.key")
		if os.path.exists(path):
			ca.key = Key(path, passphrase)
		else:
			ca.key = self.generatePrivateKey(path, passphrase)

		path = os.path.join(directory, "ca.cert")
		if os.path.exists(path):
			ca.cert = Certificate(path, ca.key)
		else:
			params = self.parametersForCA(cn)
			ca.cert = self.createSelfSignedCert(params, ca.key, path)

		return ca

	def createWebServer(self, ca, hostname, aliases = []):
		assert('/' not in hostname)
		assert(not hostname.startswith('.'))

		path = ca.getPathFor("webserver", hostname)

		server = Server(hostname)
		server.key = self.generatePrivateKey(os.path.join(path, "cert.key"))

		params = self.parametersForSSLServer(hostname)
		params.addAltSubjectName("dns", hostname)
		for alias in aliases:
			params.addAltSubjectName("dns", alias)

		req = self.createCSR(params, server.key)
		server.cert = self.signCSR(ca.cert, req, os.path.join(path, "cert.pem"))

		return server

if __name__ == '__main__':
	pki = PKI("/tmp/pki")

	ca = pki.createCA("FancyCA", passphrase = "rand0mP4ssphr4se")
	server = pki.createWebServer(ca, "foo.bar.com", aliases = ["foo2.bar.com"])

	# pki.dump(server.cert)
