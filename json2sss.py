# Convert a JSON description of a CSV file + CSV file into Triple-S XML 2.0

import exceptions
import math
import re
import traceback
from xml.sax.saxutils import escape, quoteattr

import unicodecsv

# The integer at least equal in magnitude to x
def magCeil (x):
	if x >= 0.0:
		return int (math.ceil (x))
	if int (x) == x:
		return int (x)
	return int (math.ceil (x))-1
		
def escapeOrNone (t):
	if t is None:
		return u""
	else:
		return escape (t)

# Round string length up from maximum observed to next largest power of 2
def sensibleStringLength (n):
	if sensibleStringLengths:
		result = 1
		while result < n: result *= 2
	else:
		result = n
	return result

# Find a sensible signed upper limit of magnitude for a numeric variable
# as power of 10 - 1 and return that limit and its number of digits
def next10Power (x):
	limit = 10
	result = 1
	xi = int (magCeil (abs (x)))
	while limit <= xi:
		limit *= 10
		result += 1
	return (result, limit)

def subDigits (t, x):
	result = ""
	for char in t:
		if char.isdigit ():
			result += x
		else:
			result += char
	return result
	
# Find number of columns and encoded rounded minimum and maximum for a number with
# given range and number of decimal places
		
def fieldFor (minimum, maximum, dp=0, width=None):
	if width is None: width = 0
	encodedMin = "%*.*f" % (width, dp, minimum)
	encodedMax = "%*.*f" % (width, dp, maximum)
	encodedMinusMax = "%0.*f" % (dp, -maximum)
	if minimum < 0 and len (encodedMinusMax) > len (encodedMin):
		encodedMin = encodedMinusMax
	columns = max (len (encodedMin), len (encodedMax))
	if minimum < 0:
		encodedMin = subDigits (encodedMin, '9')
	else:
		encodedMin = '0'
	encodedMax = subDigits (encodedMax, '9')
	return (columns, encodedMin, encodedMax)
	
def formatFor (columns, dp=0):
		return "%%%d.%df" % (columns, dp)
		
def forceEncoding (s):
	if s is None:
		return ""
	elif type (s) == str:
		return s
	elif type (s) == unicode:
		return s.encode (outputEncoding)
	else:
		return str (s)
		
def SSSAllocate (jsonData):
	import math
	recordLength = 0
	index = 0
	for index, variableName in enumerate (jsonData ["variable_sequence"]):
		variable = jsonData ["variables"] [variableName]
		cd = variable ["distribution"]
		jDataType = variable ["json_type"]
		if jDataType == "integer":
			(variable ["SSSWidth"],
			 variable ["SSSEncodedMinimum"],
			 variable ["SSSEncodedMaximum"]) =\
				fieldFor (cd ["min_value"], cd ["max_value"],
					  0)
			variable ["SSSType"] = "quantity"
			variable ["SSSNumericFormat"] = formatFor (variable ["SSSWidth"])
		elif jDataType == "decimal":
			(variable ["SSSWidth"],
			 variable ["SSSEncodedMinimum"],
			 variable ["SSSEncodedMaximum"]) =\
				fieldFor (cd ["min_value"], cd ["max_value"],
					  cd ["max_dp"])
			variable ["SSSType"] = "quantity"
			variable ["SSSNumericFormat"] = formatFor (variable ["SSSWidth"], cd ["max_dp"])
		elif jDataType == "string":
			variable ["SSSType"] = "character"
			variable ["SSSWidth"] = sensibleStringLength (cd ["max_text_length"])
			if variable.get ("width"):
				variable ["SSSWidth"] = min (variable ["SSSWidth"], variable ["width"])
		elif jDataType == "date":
			variable ["SSSType"] = "date"
			variable ["SSSWidth"] = 8
		elif jDataType == "time":
			variable ["SSSType"] = "time"
			variable ["SSSWidth"] = 6
		else:
			# Variables that we know nothing useful about export as character length 1
			variable ["SSSType"] = "character"
			variable ["SSSWidth"] = 1
		labelListName = variable.get ("code_list_name")
		if labelListName:
			variable ["SSSFormat"] = "numeric"
			if jDataType != "integer" or\
			   variable ["distribution"].get ("min_value") < 0:
				variable ["SSSFormat"] = "literal"
			if variable.get ("incomplete_coding") and\
			   variable ["SSSFormat"] == "literal":
				print "--Variable %s has incomplete coding" % variable ["name"]
				# Variable exported as quantity or string
			else:
				labelList = jsonData ["code_lists"] [labelListName]
				maxCodeLength = max ((len (code) for code in labelList ["table"].keys ()))
				variable ["SSSType"] = "single"
				variable ["SSSWidth"] = max (maxCodeLength, cd.get ("max_text_length"))
				if variable ["SSSFormat"] == "numeric":
					variable ["SSSNumericFormat"] = formatFor (variable ["SSSWidth"])
		variable ["start"] = recordLength + 1
		variable ["finish"] = recordLength + variable ["SSSWidth"]
		recordLength = variable ["finish"]
	return recordLength
	
def valueIterator (values):
	for valueItem in values:
		if type (valueItem) == list:
			for index in xrange (valueItem [0]):
				yield valueItem [1]
		else:
			yield valueItem

def writeXMLForVariables (jsonData, XMLFile, format="asc"):
	variables = jsonData ["variables"]
	weightName = jsonData.get ("weight_variable")
	for index, variableName in enumerate (jsonData ["variable_sequence"]):
		variable = variables [variableName]
		use = u""
		if variable ["name"] == weightName:
			use = u' use="weight"'
		filter = u""
		formatAttribute = u""
		if variable.get ("SSSFormat") == "literal":
			formatAttribute = u' format="literal"'
		if format == "asc":
			positionAttributes = u'start="%d" finish="%d"' %\
				(variable ["start"], variable ["finish"])
		else:
			positionAttributes = u'start="%d"' % (index+1,)
		result = u"""			<variable ident="%s" type=%s%s%s%s>
				<name>%s</name>
				<label>%s</label>
				<position %s/>\n""" %\
				(index+1, quoteattr(variable ["SSSType"]),
				 formatAttribute, use, filter,
				 escapeOrNone (variable ["name"]),
				 escapeOrNone (variable ["title"]),
				 positionAttributes)
		XMLFile.write (forceEncoding (result))
		if variable ["SSSType"] in ('character', 'date', 'time'):
			XMLFile.write ("""				<size>%s</size>\n""" %\
				variable ["SSSWidth"])
		else:
			XMLFile.write ("""				<values>\n""")
			if variable ["SSSType"] == 'quantity' or\
				(variable ["SSSType"] == 'single' and\
				 variable.get ("incomplete_coding") and\
				 variable ["SSSFormat"] == 'numeric'):
				XMLFile.write ("""					<range from="%s" to="%s"/>\n""" %\
					(variable ["SSSEncodedMinimum"],
					 variable ["SSSEncodedMaximum"]))
			if variable ["SSSType"] == "single":
				codeList = jsonData ["code_lists"] [variable ["code_list_name"]]
				for code in codeList ["sequence"]:
					text = codeList ["table"] [code]
					if text is None:
						text = ""
					elif type (text) == int:
						text = str (text)
					else:
						text = forceEncoding(escapeOrNone(text))
					XMLFile.write\
						("""					<value code="%s">%s</value>\n""" %\
						(forceEncoding (code), text))
			XMLFile.write ("""				</values>\n""")
		XMLFile.write ("""			</variable>\n""")

if __name__ == "__main__":
	import datetime
	import getopt
	import json
	import os.path
	import sys

	from version import savutilVersion
		
	sensibleStringLengths = True
	full = False
	outputEncoding = "Windows-1252"
	ident = "A"
	spreadMultipleAnswerList = ":1st answer,:2nd answer,:3rd answer,:4th answer,:5th answer,:6th answer,:7th answer,:8th answer"
	defaultMetadata = (";%s;%s;JSON2SSS %s (Windows) by Computable Functions (http://www.computable-functions.com)" %\
		("now", "now", savutilVersion)).split (";")
	xmlMetadata = ""
	showVersion = False
	href = ""
	titleText = ""
	csv = False
	
	optlist, args = getopt.getopt (sys.argv[1:], 'cvse:hi:x:t:')
	for (option, value) in optlist:
		if option == '-c':
			csv = True
		if option == '-e':
			outputEncoding = value
		if option == "-h":
			href = value
		if option == '-i':
			ident = value				
		if option == "-x":
			xmlMetadata = value
		if option == '-s':
			sensibleStringLengths = False
		if option == "-t":
			titleText = value
		if option == "-v":
			showVersion = True
			
	if len (args) != 1:
		print "--No JSON input file specified"
		sys.exit (0)

	nameTitle = titleText.split (";")
	if len (nameTitle) == 1:
		name = ""
		title = nameTitle [0]
	else:
		name, title = nameTitle [:2]
			
	metadataFields = xmlMetadata.split (";")
	if len (metadataFields) > 0 and len (metadataFields [0]):
		sssUser = metadataFields [0]
	else:
		sssUser = defaultMetadata [0]
	if len (metadataFields) > 1 and len (metadataFields [1]):
		sssDate = metadataFields [1]
	else:
		sssDate = defaultMetadata [1]
	if len (metadataFields) > 2 and len (metadataFields [2]):
		sssTime = metadataFields [2]
	else:
		sssTime = defaultMetadata [2]
	if len (metadataFields) > 3 and len (metadataFields [3]):
		sssOrigin = metadataFields [3]
	else:
		sssOrigin = defaultMetadata [3]
		
	if len (ident) == 1 and ident.isalpha ():
		ident = ident.upper ()
	else:
		print "--Invalid ident value: '%s'" % ident
		sys.exit (0)
				
	if showVersion:
		print "..sav2sss version %s" % savutilVersion
				
	if csv:
		format = 'csv'
		extension = '.csv'
	else:
		format = 'asc'
		extension = '.asc'
	fragments = os.path.splitext (args [0])
	root = fragments [0]
	
	print "..Converting %s to %s_sss.xml and %s_sss%s" %\
		(args [0], root, root, extension)
	if not href:
		href = "%s_sss%s" % (root, extension)
	if href:
		print "..href attribute will be '%s'" % href
		
	# Get JSON information
	try:
		jsonFile = open (root + ".json")
		jsonData = json.loads (jsonFile.read ())
		jsonFile.close ()
	except exceptions.Exception, e:
		print "--Can't load JSON file (%s)" % e
		traceback.print_exc ()
		sys.exit (0)

	try:
		print "..JSON file %s loaded, %d variable(s), %d answer list(s)" %\
			(root + ".json",
			 len(jsonData ["variable_sequence"]),
			 len(jsonData ["code_lists"]))
		#newSchema = sssxmlschema.SSSXMLSchema().convert (savSchema.schema, href)
		if not sssDate.strip () and savData.creation_date:
			sssDate = savData.creation_date
		if not sssTime.strip () and savData.creation_time:
			sssTime = savData.creation_time
		nowISO = datetime.datetime.now ().isoformat ()
		if sssDate and sssDate.lower () == 'now':
			sssDate = nowISO [:10]
		if sssTime and sssTime.lower () == 'now':
			sssTime = nowISO [11:19]
		#newSchema.sssDate = sssDate
		#newSchema.sssTime = sssTime
		#newSchema.sssOrigin = sssOrigin
		#newSchema.sssUser = sssUser
		#newSchema.ident = ident
		#newSchema.schema.name = name
		#newSchema.schema.title = title
		#newSchema.allocate()
		SSSAllocate (jsonData)
		
		outputXMLFile = open (root + "_sss.xml", 'w')
		xmlDate = ""
		if sssDate and sssDate.strip ():
			xmlDate = "\n\t<date>%s</date>" % sssDate
		xmlTime = ""
		if sssTime and sssTime.strip ():
			xmlTime = "\n\t<time>%s</time>" % sssTime
		xmlOrigin= ""
		if sssOrigin and sssOrigin.strip ():
			xmlOrigin = "\n\t<origin>%s</origin>" % sssOrigin
		xmlUser = ""
		if sssUser and sssUser.strip ():
			xmlUser = "\n\t<user>%s</user>" % sssUser
		xmlName = ""
		if name:
			xmlName = "\n\t\t<name>%s</name>" %\
				forceEncoding (escapeOrNone(name))
		xmlTitle = ""
		if title:
			xmlTitle = "\n\t\t<title>%s</title>" %\
				forceEncoding (escapeOrNone(title))
		recordAttributes = " ident=\"%s\"" % ident
		if href.strip ():
			recordAttributes += " href=\"%s\"" %\
				forceEncoding(escapeOrNone (href.strip ()))
		if format == "csv":
			recordAttributes += " format=\"csv\" skip=\"1\""
		outputXMLFile.write ("""<?xml version="1.0" encoding="%s"?>
<sss version="2.0">%s%s%s%s
	<survey>%s%s
		<record%s>\n""" %\
			(outputEncoding, xmlDate, xmlTime, xmlOrigin, xmlUser,
			 xmlTitle,
			 xmlName,
			 recordAttributes))
		writeXMLForVariables (jsonData, outputXMLFile, format)
		outputXMLFile.write ("""		</record>
	</survey>
</sss>
""")
		outputXMLFile.close ()
		
		outputDataFilename = root + "_sss" + extension
		# We can't use the bare data values because we have to reformat time/date and
		# justify fixed-format fields
		datafile = open (outputDataFilename, "wb")
		if format == "csv":
			CSVFile = unicodecsv.writer (datafile, encoding=outputEncoding)
			CSVFile.writerow (jsonData ["variable_sequence"])
		variableIterators = [valueIterator (jsonData ["data"] [variableName])
			for variableName in jsonData ["variable_sequence"]]
		variableTypes = [jsonData ["variables"] [variableName] ["SSSType"]
			for variableName in jsonData ["variable_sequence"]]
		variableWidths = [jsonData ["variables"] [variableName] ["SSSWidth"]
			for variableName in jsonData ["variable_sequence"]]
		numLits = [jsonData ["variables"] [variableName].get ("SSSFormat")
			for variableName in jsonData ["variable_sequence"]]
		numericFormats = [jsonData ["variables"] [variableName].get ("SSSFormat")
			for variableName in jsonData ["variable_sequence"]]
		fieldData = [(
			valueIterator (jsonData ["data"] [variableName]),
			jsonData ["variables"] [variableName] ["SSSType"],
			jsonData ["variables"] [variableName] ["SSSWidth"],
			jsonData ["variables"] [variableName] .get ("SSSFormat"),
			jsonData ["variables"] [variableName] .get ("SSSNumericFormat")
		) for variableName in jsonData ["variable_sequence"]]
		for sequence in xrange (jsonData ["total_count"]):
			record = []
			for index, (rawValue, variableType, width, numLit, numericFormat)\
				in enumerate (fieldData):
				value = rawValue.next ()
				if value is None:
					value = u""
				else:
					if variableType == "quantity" or\
					   (variableType == "single" and numLit == "numeric"):
						value = numericFormat % value
					if variableType == "date":
						value = value [:4] + value [5:7] + value [8:]
					elif variableType == "time":
						value = value [:2] + value [3:5] + value [6:]
				if format == "asc":
					if variableType == "character" or\
					   (variableType == "single" and numLit == "literal"):
						value = unicode (value).ljust (width)
					else:
						value = unicode (value).rjust (width)
				record.append (value)
			if format == "csv":
				CSVFile.writerow (record)
			else:
				datafile.write (forceEncoding(u"".join (record).rstrip () + u"\n"))				
		datafile.close ()
		
	except UnicodeEncodeError, e:
		print "--Can't render this file in encoding '%s', use -e to specify another encoding" %\
			outputEncoding
		traceback.print_exc ()

	except exceptions.Exception, e:
		print "--Cannot prepare triple-S XML dataset (%s)" % e
		traceback.print_exc ()

