#!/usr/bin/python
#
# chicken.py - Encrypts and uploads AmigaOS files for beta testing
# Copyright (C) 2021 Steven Solie
# 
# This is a Python version of the infamous chicken program
# which I call 'chicken pie' for obvious reasons. If you don't
# know what chicken is then you don't need this.
#
# The original chicken program is by Olaf Barthel.
#
# If run on AmigaOS, chicken pie will use your preconfigured PGP
# key ring just as the original chicken program does.
#
# If run on any amd64-based platform with Docker, chicken pie will
# use the ssolie/pgp-chicken:latest Docker image to perform the
# PGP encryption step.
#
# If a file named chicken.config is present it will be parsed to
# obtain the destination FTP server, user, password and upload
# directory. The command line equivalents override the settings
# in the config file.
#
# Compatible with Python 2.5 and higher.
#
# Special thanks to https://regex101.com/ for the assistance.
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

import sys
import os
import getopt
import re
import ftplib

# Embedded version string.
version = '$VER: chicken.py 54.1 (16.11.2021)'

# Default config parameters.
pgp_recipient = 'beta4ups'
docker_image = 'ssolie/pgp-chicken:latest'

# Regex for the file names.
file_name_regex = re.compile(r"^[a-z0-9_-]+-([0-9]+).([0-9]+).lha")

# Default command line arguments.
args = {
	'h':        False,
	'ftp_host': 'unknown',
	'ftp_user': 'none',
	'ftp_pass': 'none',
	'ftp_dir':  None,
	'infiles':  None
}

def print_usage():
	print("Usage: chicken.py [option] files")
	print("   -h : Print help")
	print("   -n : FTP destination host name")
	print("   -u : FTP user name")
	print("   -p : FTP password")
	print("   -d : FTP destination directory")
	print("files : Input files")

def parse_args():
	""" Parse command line arguments
	"""
	try:
		opts, files = getopt.getopt(sys.argv[1:], "hn:u:p:d:")
	except getopt.GetoptError:
		return False

	for opt, val in opts:
		if opt == '-h':
			args['h'] = True
		
		if opt == '-n':
			args['ftp_host'] = val

		if opt == '-u':
			args['ftp_user'] = val

		if opt == '-p':
			args['ftp_pass'] = val

		if opt == '-d':
			args['ftp_dir'] = val

	if (len(files)) < 1:
		args['h'] = True
	else:
		args['infiles'] = files

	return True

def parse_config(filename):
	""" Parse config file which consists of key=value pairs.
	"""
	cfgfile = None
	try:
		cfgfile = open(filename, 'r')
	except:
		pass

	if cfgfile != None:
		lines = cfgfile.readlines()
		for line in lines:
			# Skip empty lines and comments
			if not line.strip() or line[0] == '#':
				continue

			# Remove all whitespace
			line = ''.join(line.split())

			# Parse key/value pair
			line = line.split('=')
			#print(line)

			if line[0] == 'destination_site':
				args['ftp_host'] = line[1]
			elif line[0] == 'destination_login':
				args['ftp_user'] = line[1]
			elif line[0] == 'destination_password':
				args['ftp_pass'] = line[1]
			elif line[0] == 'destination_dir':
				args['ftp_dir'] = line[1]

def encrypt_file(infile):
	""" Encrypt file using pgp 2.6.3
	"""
	outfile = infile + '.pgp'
	inpath = os.path.dirname(os.path.realpath(infile))
	infile_pgp = infile + '.pgp'

	# Be sure the destination file doesn't exist or the
	# pgp encryption step will fail.
	try:
		os.remove(infile_pgp)
	except:
		pass

	cmd = None

	# When running on AmigaOS we just use the pre-installed PGP.
	#
	# When running on anything else use the Docker image.
	if os.name == 'amiga':
		cmd_infile = infile
		cmd_outfile = outfile

		cmd = 'pgp -o ' + cmd_outfile + ' -e ' + cmd_infile + ' '
		cmd += pgp_recipient
	else:
		cmd_infile = '/tmp/' + infile
		cmd_outfile = '/tmp/' + outfile

		cmd = 'docker run --rm '
		cmd += '-v ' + inpath + ':/tmp '
		cmd += '-w /root '
		cmd += docker_image + ' '
		cmd += './pgp -o ' + cmd_outfile + ' -e ' + cmd_infile + ' '
		cmd += pgp_recipient

	res = os.system(cmd)
	if res == 0:
		return outfile
	else:
		return None

def send_file(outpath, ftphost, ftpuser, ftppass, ftpdir):
	outfile = None

	try:
		outfile = open(outpath, 'rb')
	except:
		print('cannot open output file')
		return False

	print('Opening FTP connection to ' + ftphost)
	print('User: ' + ftpuser + ' Password: ' + ftppass)

	if ftpdir != None:
		print('Directory: ' + ftpdir)

	try:
		ftp = ftplib.FTP(ftphost, ftpuser, ftppass)
	except:
		print('failed to connect')
		return False

	try:
		ftp_stor = 'STOR ' + outpath
		print(ftp_stor)

		if ftpdir != None:
			ftp.cwd(ftpdir)

		ftp.storbinary(ftp_stor, outfile)
		ftp.quit()
	except:
		print('failed to upload')
		return False

	return True

def valid_file_name(name):
	match = file_name_regex.match(name)
	if not match:
		print('1. File name must end with ".lha"')
		print("2. File name must consist of a label part and a version.revision part separated by '-'.")
		print("3. Label part must consist of a non-empty sequence of lower case letters, digits, '-' or '_'.")
		print("4. The version.revision part must consist of non-empty sequences of digits. Neither sequence of digits may begin with a '0'.")
		return False
	
	ver = match.group(1)
	rev = match.group(2)

	if len(ver) > 1 and ver[0] == '0':
		print('version cannot have a leading zero')
		return False

	# The version number must not be larger than 255 because
	# a 'struct Resident' uses an 8 bit unsigned integer.
	if int(ver) > 255:
		print('version cannot be greater than 255')
		return False

	if len(rev) > 1 and rev[0] == '0':
		print('revision cannot have a leading zero')
		return False

	# The revision number must not be larger than 65535 because
	# a 'struct Library' uses a 16 bit unsigned integer.
	if int(rev) > 65535:
		print('revision cannot be greater than 65535')
		return False

	return True

if __name__ == "__main__":
	parse_config('chicken.config')

	if not parse_args():
		print_usage()
		exit(1)

	if args['h']:
		print_usage()
		exit(1)

	for arg in args['infiles']:
		inpath = os.path.normpath(arg)

		if not os.path.exists(inpath):
			print('does not exist')
			break

		if not os.path.isfile(inpath):
			print('not a file')
			break

		if not valid_file_name(inpath):
			break

		print('Encrypting ' + inpath)
		outpath = encrypt_file(inpath)
		if outpath == None:
			print('pgp encryption failed')
			break

		print('Sending ' + outpath)
		if not send_file(outpath, args['ftp_host'], args['ftp_user'], args['ftp_pass'], args['ftp_dir']):
			break

		print('Done')
