#!/usr/bin/python3
#
# nginx application driver
#
# Test scripts that require an nginx service running on a given SUT would do one of these:
#
# Inside the run script:
#
#	import farthings.application.nginx
#
# Inside testcase.conf
#
#	node server {
#		application nginx;
#	}
#
# Copyright (C) 2022 Olaf Kirch <okir@suse.de>

import susetest
import twopence
import os

from farthings.openssl_pki import PKI

class NginxConfig:
	def __init__(self, target, fileResource):
		self.target = target
		self.resource = fileResource
		self._editor = None

	@property
	def editor(self):
		if self._editor is None:
			if self.resource is None:
				raise ValueError("Did not find nginx.conf")

			self._editor = self.resource.createEditor()
		return self._editor

	def commit(self):
		if self._editor is None:
			return True

		if not self._editor.commit():
			self.target.logFailure("Unable to commit modified nginx.conf")
			return False

		return True

	@property
	def isLocal(self):
		return self.editor.proxy.isLocal

	def addFile(self, data, name):
		# These are file proxy objects that hide where these files live, and
		# how to access them
		dir = self.editor.proxy.parentDirectory
		fileProxy = dir.createFile(name)

		twopence.debug(f"Writing {fileProxy.path}")
		fileProxy.write(data)

		return name

	# FIXME: this should operate on FileProxy objects instead of local path names.
	def uploadFile(self, localPath, name):
		with open(localPath, "rb") as f:
			name = self.addFile(f.read(), name)
		return name

	def makeKey(self, args):
		return self.editor.makeKey(args)

	@property
	def httpBlock(self):
		return self.getUniqueBlock("http")
	
	def getUniqueBlock(self, name):
		key = self.makeKey(name)
		return self._editor.lookupEntry(key)

	# This is how you look for all server blocks nested inside the http block
	@property
	def httpServers(self):
		return iter(self.matchHttpServers())

	def matchHttpServers(self, server_name = None, port = None):
		primaryKeys = [
			self.makeKey("http"),
			self.makeKey("server")
		]

		secondaryKeys = []
		if server_name:
			secondaryKeys.append(self.makeKey(["server_name", server_name]))
		if port:
			secondaryKeys.append(self.makeKey(["listen", str(port)]))

		for block in self._editor.lookupEntryNested(primaryKeys):
			if all(block.hasEntry(key) for key in secondaryKeys):
				yield NginxServer(block)

	def findHttpServerUnique(self, **kwargs):
		found = list(self.matchHttpServers(**kwargs))
		if not found:
			return None
		if len(found) > 1:
			raise KeyError(f"found multiple servers for {kwargs}")
		return found[0]

	def createServer(self, hostname = "localhost", aliases = [], port = None, ssl = False):
		if port is None:
			port = ssl and 443 or 80
			print(f"Creating server on port {port}")

		server = self.findHttpServerUnique(port = port)
		if server is None:
			block = self.httpBlock.createBlock("server")
			server = NginxServer(block)
			server.setPort(443, ssl = ssl)

		server.fqdn = hostname
		server.aliases = aliases
		print(f"Created new server fqdn={server.fqdn} aliases={server.aliases}")

		return server

class BlockBackedObject:
	def __init__(self, block):
		self._block = block

	def _get_value(self, keyword):
		p = self._block.getProperty(keyword)
		if p is not None:
			return p.value

	def _get_values(self, keyword):
		p = self._block.getProperty(keyword)
		if p is not None:
			return p.values
		return []

	def _set_value(self, keyword, value):
		self._block.setProperty(keyword, value)

	def _set_values(self, keyword, values):
		self._block.setProperty(keyword, values)

class NginxServer(BlockBackedObject):
	def __init__(self, block, hostname = None, aliases = []):
		super().__init__(block)

		self.cacheClearFQDN()

		if hostname or aliases:
			self._fqdn = hostname
			self._aliases = aliases
			self.cacheWritebackFQDN()

	@property
	def url(self):
		host = self.fqdn

		port = self.port
		if ':' in port:
			port = port.split(':')[-1]

		if 'ssl' in self._block.getProperty("listen").values:
			proto = "https"
		else:
			proto = "http"

		if proto == "http" and str(port) == "80":
			return f"{proto}://{host}/"
		if proto == "https" and str(port) == "443":
			return f"{proto}://{host}/"

		return f"{proto}://{host}:{port}/"

	@property
	def port(self):
		p = self._block.getProperty("listen")
		if p is None:
			return None

		# The listen statement comes in different shapes, eg
		#	listen 80;
		#	listen 443 ssl;
		#	listen hostname:8080;
		values = p.values
		if not values:
			return None

		return values[0]

	def setPort(self, port, ssl = False):
		values = [str(port)]
		if ssl:
			values.append("ssl")

		self._block.setProperty("listen", values)

	@property
	def server_name(self):
		# The server_name statement comes in different shapes, eg
		#	server_name "www.blah.com";
		#	server_name "www.blah.com" alias "www.l33t.com";
		return self._get_value("server_name")

	@server_name.setter
	def server_name(self, value):
		self._set_value("server_name", value)
		self.cacheClearFQDN()

	@property
	def fqdn(self):
		self.cacheFQDN()
		return self._fqdn

	@fqdn.setter
	def fqdn(self, name):
		self.cacheFQDN()
		self._fqdn = name
		self.cacheWritebackFQDN()

	@property
	def aliases(self):
		self.cacheFQDN()
		return self._aliases

	@aliases.setter
	def aliases(self, names):
		self.cacheFQDN()
		self._aliases = names
		self.cacheWritebackFQDN()

	def cacheFQDN(self):
		if self._fqdn is not None:
			return

		names = self._get_values("server_name")
		if not names:
			return

		self._fqdn = names.pop(0)
		while names:
			word = names.pop(0)
			if word != 'alias' or not names:
				words = self._get_values("server_name")
				raise ValueError(f"Unable to process \"server_name {words}\"")
			self._aliases.append(names.pop(0))

	def cacheWritebackFQDN(self):
		assert(self._fqdn is not None)
		values = [self._fqdn]
		for alias in self._aliases:
			values += ["alias", alias]
		self._set_values("server_name", values)

	def cacheClearFQDN(self):
		self._fqdn = None
		self._aliases = []

	@property
	def charset(self):
		return self._get_value("server_name")

	@charset.setter
	def charset(self, value):
		self._set_value("charset", value)

	def format(self):
		return self._block.format()

	@property
	def ssl_certificate(self):
		return self._get_value("ssl_certificate")
	
	@ssl_certificate.setter
	def ssl_certificate(self, value):
		self._set_value("ssl_certificate", value)

	@property
	def ssl_certificate_key(self):
		return self._get_value("ssl_certificate_key")
	
	@ssl_certificate_key.setter
	def ssl_certificate_key(self, value):
		self._set_value("ssl_certificate_key", value)

	@property
	def ssl_protocols(self):
		return self._get_values("ssl_protocols")
	
	@ssl_protocols.setter
	def ssl_protocols(self, values):
		self._set_values("ssl_protocols", values)

	@property
	def hasSSL(self):
		return self.ssl_certificate_key and self.ssl_certificate

	def findLocation(self, path):
		found = list(self._block.matchBlocks(["location", path]))
		if not found:
			return None
		if len(found) > 1:
			raise KeyError(f"found multiple locations for {path}")
		return NginxLocation(found[0])

	def createLocation(self, path):
		loc = self.findLocation(path)
		if loc:
			return loc

		block = self._block.createBlock(["location", path])
		return NginxLocation(block)

class NginxLocation(BlockBackedObject):
	@property
	def root(self):
		return self._get_value("root")
	
	@root.setter
	def root(self, value):
		return self._set_value("root", value)

	@property
	def index(self):
		return self._get_values("index")

	@index.setter
	def index(self, values):
		return self._set_values("index", values)

class NginxApplication(susetest.Application):
	id = "nginx"
	service_name = "nginx"

	def __init__(self, driver, target):
		super().__init__(driver, target)

		configResource = target.requireFile("nginx.conf")
		if configResource is None:
			raise ValueError("Did not find nginx.conf")

		self.config = NginxConfig(target, configResource)

		documentResource = target.requireDirectory("htdocs")
		if documentResource is None:
			raise ValueError("Did not find htdocs")

		self.documentRoot = documentResource.path
		target.logInfo(f"Nginx document root is {self.documentRoot}")

		# We could turn PKI into an application as well
		self.pki = PKI(driver.workspace)
		self.ca = None

		if not self.config.isLocal:
			self.pki.configureTarget(target)

	@property
	def CA(self):
		if self.ca is None:
			self.ca = self.pki.createCA("FancyCA", passphrase = "rand0mP4ssphr4se")
		return self.ca

	# FIXME: this should return a FileProxy, not a path
	@property
	def CACertificate(self):
		if self.ca is None:
			return None
		return self.ca.cert

	def createServer(self, **kwargs):
		withSSL = kwargs.get('ssl')

		server = self.config.createServer(**kwargs)

		if withSSL and not server.hasSSL:
			self.createServerCertificate(server, server.fqdn, server.aliases)

		loc = self.populateLocationDefaults(server, "/")
		return server

	def createServerCertificate(self, server, hostname = None, aliases = []):
		if hostname is None:
			hostname = self.target.fqdn()
		print("hostname is", hostname)

		sslID = self.pki.createWebServer(self.CA, hostname, aliases = aliases)

		# Now copy the certificates to /etc/nginx
		server.ssl_certificate = self.config.uploadFile(sslID.cert.path, f"{hostname}.pem")
		server.ssl_certificate_key = self.config.uploadFile(sslID.key.path, f"{hostname}.key")
		server.ssl_protocols = ["TLSv1.2"]

		return sslID

	def populateLocationDefaults(self, server, path):
		loc = server.createLocation(path)
		if loc.root is None:
			loc.root = self.documentRoot
			if not loc.root.endswith("/"):
				loc.root += "/"
		if not loc.index:
			loc.index = ["index.html", "index.htm"]
		return loc

	def uploadIndexFile(self, data, name = "index.html"):
		path = os.path.join(self.documentRoot, name)
		if not self.target.sendbuffer(path, data, user = "root"):
			self.target.logFailure(f"Unable to upload to {path}")
			return False

		return True

	def serverUrls(self, **kwargs):
		for server in self.config.matchHttpServers(**kwargs):
			yield server.url
