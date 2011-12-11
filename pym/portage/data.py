# data.py -- Calculated/Discovered Data Values
# Copyright 1998-2011 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2

import os, pwd, grp, platform

import portage
portage.proxy.lazyimport.lazyimport(globals(),
	'portage.output:colorize',
	'portage.util:writemsg',
)
from portage.localization import _

ostype=platform.system()
userland = None
if ostype == "DragonFly" or ostype.endswith("BSD"):
	userland = "BSD"
else:
	userland = "GNU"

lchown = getattr(os, "lchown", None)

if not lchown:
	if ostype == "Darwin":
		def lchown(*pos_args, **key_args):
			pass
	else:
		def lchown(*pargs, **kwargs):
			writemsg(colorize("BAD", "!!!") + _(
				" It seems that os.lchown does not"
				" exist.  Please rebuild python.\n"), noiselevel=-1)
		lchown()

lchown = portage._unicode_func_wrapper(lchown)

def portage_group_warning():
	warn_prefix = colorize("BAD", "*** WARNING ***  ")
	mylines = [
		"For security reasons, only system administrators should be",
		"allowed in the portage group.  Untrusted users or processes",
		"can potentially exploit the portage group for attacks such as",
		"local privilege escalation."
	]
	for x in mylines:
		writemsg(warn_prefix, noiselevel=-1)
		writemsg(x, noiselevel=-1)
		writemsg("\n", noiselevel=-1)
	writemsg("\n", noiselevel=-1)

# Portage has 3 security levels that depend on the uid and gid of the main
# process and are assigned according to the following table:
#
# Privileges  secpass  uid    gid
# normal      0        any    any
# group       1        any    portage_gid
# super       2        0      any
#
# If the "wheel" group does not exist then wheelgid falls back to 0.
# If the "portage" group does not exist then portage_uid falls back to wheelgid.

uid=os.getuid()
wheelgid=0

try:
	wheelgid=grp.getgrnam("wheel")[2]
except KeyError:
	pass

# The portage_uid and portage_gid global constants, and others that
# depend on them are initialized lazily, in order to allow configuration
# via make.conf. Eventually, these constants may be deprecated in favor
# of config attributes, since it's conceivable that multiple
# configurations with different constants could be used simultaneously.
_initialized_globals = set()

def _get_global(k):
	if k in _initialized_globals:
		return globals()[k]

	if k in ('portage_gid', 'portage_uid', 'secpass'):
		global portage_gid, portage_uid, secpass
		secpass = 0
		if uid == 0:
			secpass = 2
		elif portage.const.EPREFIX:
			secpass = 2
		#Discover the uid and gid of the portage user/group
		try:
			portage_uid = pwd.getpwnam(_get_global('_portage_username')).pw_uid
			portage_gid = grp.getgrnam(_get_global('_portage_grpname')).gr_gid
			if secpass < 1 and portage_gid in os.getgroups():
				secpass = 1
		except KeyError:
			portage_uid = 0
			portage_gid = 0
			writemsg(colorize("BAD",
				_("portage: 'portage' user or group missing.")) + "\n", noiselevel=-1)
			writemsg(_(
				"         For the defaults, line 1 goes into passwd, "
				"and 2 into group.\n"), noiselevel=-1)
			writemsg(colorize("GOOD",
				"         portage:x:250:250:portage:/var/tmp/portage:/bin/false") \
				+ "\n", noiselevel=-1)
			writemsg(colorize("GOOD", "         portage::250:portage") + "\n",
				noiselevel=-1)
			portage_group_warning()

		_initialized_globals.add('portage_gid')
		_initialized_globals.add('portage_uid')
		_initialized_globals.add('secpass')

		if k == 'portage_gid':
			return portage_gid
		elif k == 'portage_uid':
			return portage_uid
		elif k == 'secpass':
			return secpass
		else:
			raise AssertionError('unknown name: %s' % k)

	elif k == 'userpriv_groups':
		v = [portage_gid]
		if secpass >= 2:
			# Get a list of group IDs for the portage user. Do not use
			# grp.getgrall() since it is known to trigger spurious
			# SIGPIPE problems with nss_ldap.
			mystatus, myoutput = \
				portage.subprocess_getstatusoutput("id -G %s" % _portage_username)
			if mystatus == os.EX_OK:
				for x in myoutput.split():
					try:
						v.append(int(x))
					except ValueError:
						pass
				v = sorted(set(v))

	# Avoid instantiating portage.settings when the desired
	# variable is set in os.environ.
	elif k == '_portage_grpname':
		v = None
		if 'PORTAGE_GRPNAME' in os.environ:
			v = os.environ['PORTAGE_GRPNAME']
		elif hasattr(portage, 'settings'):
			v = portage.settings.get('PORTAGE_GRPNAME')
		if v is None:
			v = 'portage'
	elif k == '_portage_username':
		v = None
		if 'PORTAGE_USERNAME' in os.environ:
			v = os.environ['PORTAGE_USERNAME']
		elif hasattr(portage, 'settings'):
			v = portage.settings.get('PORTAGE_USERNAME')
		if v is None:
			v = 'portage'
	else:
		raise AssertionError('unknown name: %s' % k)

	globals()[k] = v
	_initialized_globals.add(k)
	return v

class _GlobalProxy(portage.proxy.objectproxy.ObjectProxy):

	__slots__ = ('_name',)

	def __init__(self, name):
		portage.proxy.objectproxy.ObjectProxy.__init__(self)
		object.__setattr__(self, '_name', name)

	def _get_target(self):
		return _get_global(object.__getattribute__(self, '_name'))

for k in ('portage_gid', 'portage_uid', 'secpass', 'userpriv_groups',
	'_portage_grpname', '_portage_username'):
	globals()[k] = _GlobalProxy(k)
del k

def _init(settings):
	"""
	Use config variables like PORTAGE_GRPNAME and PORTAGE_USERNAME to
	initialize global variables. This allows settings to come from make.conf
	instead of requiring them to be set in the calling environment.
	"""
	if '_portage_grpname' not in _initialized_globals and \
		'_portage_username' not in _initialized_globals:

		v = settings.get('PORTAGE_GRPNAME', 'portage')
		globals()['_portage_grpname'] = v
		_initialized_globals.add('_portage_grpname')

		v = settings.get('PORTAGE_USERNAME', 'portage')
		globals()['_portage_username'] = v
		_initialized_globals.add('_portage_username')
