# Copyright (c) 2014, 2015 Computable Functions Limited, UK

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# setup.py for savjson and json2sss

import sys

from distutils.core import setup
import py2exe
import os.path

from version import savutilVersion

includes = ['encodings', 'encodings.*']

options = {
	"py2exe": {
		'bundle_files': 1,
		'compressed': True,
		"includes": includes
	}
}

setup(
      console=["sav2json.py"],
      author="Iain MacKay",
      author_email="iain@computable-functions.com",
      contact="Iain MacKay",
      options=options,
      contact_email="support@computable-functions.com",
      description="savjson - convert .sav data into a JSON format",
      name="sav2json",
      zipfile=None,
      version=savutilVersion)

setup(
      console=["json2sss.py"],
      author="Iain MacKay",
      author_email="iain@computable-functions.com",
      contact="Iain MacKay",
      options=options,
      contact_email="iain@computable-functions.com",
      description="json2sss - export json survey data to Triple-S",
      name="json2sss",
      zipfile=None,
      version=savutilVersion)
