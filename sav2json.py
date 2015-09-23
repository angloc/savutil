# savJSON
#
# Converts a .sav file and its metadata to a JSON format. This format mitigates the difficulties caused by:
#
#	Excess allocation of string variable lengths
#	Duplication of value label lists
#	Complex specification of missing values
#	Diversity of numeric formats
#	Incomplete value label lists
#	Diversity of date-time formats
#	Encoding issues - JSON is output by default as ASCII with individual non-ASCII codes escaped

import contextlib
import itertools
import exceptions
import math
import re
import sys

import savdllwrapper
import unicodecsv

import classifiedunicodevalue
from classifiedunicodevalue import ClassifiedUnicodeValue

formatRE = re.compile ("([A-Z]+)(\d+)(\.(\d+))?")

SPSSDateFormats = {
	'DATE': u"date",
	'ADATE': u"date",
	'EDATE': u"date",
	'JDATE': u"date",
	'SDATE': u"date",
	'QYR': u"date",
	'MOYR': u"date",
	'WKYR': u"date",
	'WKDAY': u"date",
	'MONTH': u"date",
	'DATETIME': u"dateTime",
	'TIME': u"time"
}

def blankNone (t):
	if t is not None: return unicode (t)
	return ""
	
def formatDP (v, dp):
	if v is None:
		return None
	elif dp is None or type (v) == unicode:
		return v
	elif dp > 0:
		return ("%0.*f" % (dp, v)).rstrip ("0").rstrip (".")
	else:
		return ("%0.0f" % v)

def omitMissing (value, treatment, systemMissing=None):
	if value == systemMissing:
		return None
	if treatment is None:
		return value
	values = treatment.get ("values")
	if values:
		if value in values:
			return None
		else:
			return value
	singleton = treatment.get ("values")
	if singleton is not None:
		if value == singleton:
			return None
		else:
			return value
	lower = treatment.get ("lower")
	upper = treatment.get ("upper")
	if lower is not None and upper is not None:
		if value < lower or value > upper:
			return value
		else:
			return None
	return value
				
class SAVVariable:
	def __init__ (self, dataset, index):

		self.index = index
		self.name = dataset.varNames [index]
		self.label = dataset.varLabels [self.name]
		self.missingValues = dataset.missingValues.get (self.name)
		self.isDummy = False
		self.format = dataset.formats.get (self.name)
		parsedFormat = formatRE.match (self.format)
		self.width = None
		self.dp = None
		self.isDateTime = False
		self.isInterval = False
		self.jsonType = None
		if parsedFormat:
			bareFormat = parsedFormat.group (1)
			self.width = int (parsedFormat.group (2))
			if parsedFormat.group (4):
				self.dp = int (parsedFormat.group (4))
			if SPSSDateFormats.get (bareFormat) is not None:
				self.jsonType = SPSSDateFormats [bareFormat]
			elif bareFormat == "TIME":
				self.jsonType = "time"
			elif bareFormat == "DTIME":
				self.jsonType = "duration"
		self.isWeight = self.name == dataset.caseWeightVar
		self.multRespDef = dataset.multRespDefs.get (self.name)
		self.varType = dataset.varTypes.get (self.name)
		
	def toObject (self):
		result = {
			'name': self.name,
			'title': self.label,
			'application_format': self.format,
			'distribution': self.cd.toObject (includeTotal=False)
		}
		result ["json_type"] = self.jsonType
		if self.width:
			result ["width"] = self.width
		if self.multRespDef:
			result ["spss_multiple_response_definition"] = self.multRespDef
		return result
		
def compressedValueSequence (s, jsonType=None):
	length = sum (1 for _ in s [1])
	value = s [0]
	if value is not None:
		if jsonType == "integer": value = int (value)
		elif jsonType == "decimal": value = float (value)
	if length == 1:
		return value
	else:
		return (length, value)
	
class SAVDataset:
	def __init__ (self, savFilename, sensibleStringLengths=True):
		self.savFilename = savFilename
		self.sensibleStringLengths = sensibleStringLengths
		with savdllwrapper.SavHeaderReader(savFilename, ioUtf8=True) as spssDict:
			dictionary = spssDict.dataDictionary()
		reader = savdllwrapper.SavReader (savFilename, ioUtf8=True)
		self.reader = reader
		self.textInfo = reader.textInfo	# Documentation text
		(self.numVars, self.nCases, self.varNames, self.varTypes,
		 self.formats, self.varLabels, self.valueLabels) = reader.getSavFileInfo()
		self.nameIndex = {}
		for index, name in enumerate (self.varNames):
			self.nameIndex [name] = index
		self.missingValues = reader.missingValues
		self.missingValuesList = [None]*len (self.varNames)
		for name, missingValuesTreatment in self.missingValues.items ():
			self.missingValuesList [self.nameIndex [name]] = missingValuesTreatment
		self.formats = reader.formats
		self.multRespDefs = reader.multRespDefs
		self.columnWidths = reader.columnWidths
		self.caseWeightVar = reader.caseWeightVar
		self.variables = [SAVVariable (self, index)
			for index, varName in enumerate (self.varNames)]
		self.originalEncoding = reader.fileEncoding
		self.title = reader.fileLabel
		major, minor, fixPack = reader.spssVersion
		if major != 0:
			self.SPSSVersion = "SPSS version %s.%s-%s" % (major, minor, fixPack)
		else:
			self.SPSSVersion = "Unknown SPSS version"
		self.dpList = [variable.dp for variable in self.variables]
		self.records = []
		#for record in reader:
		#	newRecord = []
		#	for index, col in enumerate (record):
		#		nonMissing = omitMissing (col, self.missingValuesList [index])
		#		cuv = ClassifiedUnicodeValue (nonMissing).value
		#		value = formatDP (cuv, self.dpList [index])
		#		newRecord.append (value)
		#	self.records.append (newRecord)
			
		self.records = [[formatDP (ClassifiedUnicodeValue
					(omitMissing (col, self.missingValuesList [index])).value,
					   self.dpList [index])
				 for index, col in enumerate (record)]
			for record in reader]
		self.normalisedValueLabels = {}
		for index, variable in enumerate (self.variables):
			distribution = {}
			name = self.varNames [index]
			valueLabels = self.valueLabels.get (name)
			if valueLabels:
				normalisedValueLabels = {}
				for value, label in valueLabels.items ():
					normalisedValue = formatDP (ClassifiedUnicodeValue (omitMissing (value,
						self.missingValuesList [index])).value, self.dpList [index])
					#normalisedLabel = ClassifiedUnicodeValue (label).value
					#if normalisedValue is not None and normalisedLabel != normalisedValue:
					#	normalisedValueLabels [normalisedValue] = normalisedLabel
					if normalisedValue != "":
						normalisedValueLabels [normalisedValue] = label
				self.normalisedValueLabels [name] = normalisedValueLabels
			variable.incompleteCoding = False
			for value in self.variableValues (index):
				if distribution.has_key (value):
					distribution [value] += 1
				else:
					distribution [value] = 1
					if valueLabels and value is not None\
						and not normalisedValueLabels.has_key (value):
						variable.incompleteCoding = True
			variable.cd = classifiedunicodevalue.ClassifiedDistribution (distribution)
			if variable.jsonType is None:
				if variable.cd.dataType == "integer":
					variable.jsonType = "integer"
					variable.dp = None
				elif variable.cd.dataType == "decimal":
					variable.jsonType = "decimal"
				elif variable.cd.dataType == "text":
					variable.jsonType = "string"
				else:
					variable.jsonType = "null"
			
	def variableValues (self, index):
		return (record [index] for record in self.records)

	def toObject (self, includeValues=False):
		result = {
			"origin": "%s from %s" % (savJSONVersion, self.SPSSVersion),
			"application_format_namespace": "http://triple-s.org/savJSON"
		}
		if self.caseWeightVar:
			result ["weight_variable"] = self.caseWeightVar
		if self.title:
			result ["title"] = self.title
		listHashMap = {}
		uniqueLists = {}
		uniqueListMap = {}
		for name, vTable in self.valueLabels.items ():
			missingTreatment = self.missingValues [name]
			newList = {}
			for code, label in vTable.items ():
				missing = missingTreatment and (omitMissing (code, missingTreatment) is None)
				if not missing:
					# We receive integer codes as reals encoded as texts
					normalisedCode = classifiedunicodevalue.ClassifiedUnicodeValue (code).value
					newList [normalisedCode] = label.strip ()
			if len (newList) == 0: continue
			newListHash = json.dumps (newList)
			existingListName = listHashMap.get (newListHash)
			if not existingListName:
				listHashMap [newListHash] = name
				uniqueLists [name] = newList
				existingListName = name
			uniqueListMap [name] = existingListName
				
		result ["code_lists"] = uniqueLists
		result ["variable_sequence"] = [variable.name for variable in self.variables]
		result ["variables"] = {}
		result ["total_count"] = len (self.records)
		for index, variable in enumerate (self.variables):
			variableObject = variable.toObject ()
			variableObject ["sequence"] = index + 1
			codeList = uniqueListMap.get (variable.name)
			if codeList:
				variableObject ["code_list_name"] = codeList
				variableObject ["incomplete_coding"] =\
					variable.incompleteCoding
			result ["variables"] [variable.name] = variableObject
		if includeData:
			result ["data"] = {}
			for index, variable in enumerate (self.variables):
				result ["data"] [variable.name] = [compressedValueSequence (s, variable.jsonType)
					for s in itertools.groupby\
						(self.variableValues (index), lambda x: x)]
		return result
			
if __name__ == "__main__":

	savJSONVersion = "savJSON 0.1"

	import getopt
	import json
	import os.path
	import sys
	import traceback
		
	outputJSON = False
	outputCSV = False
	outputPath = "."
	outputEncoding = "cp1252"
	printVersion = False
	outputText = False
	header = False
	interpretCodes = False
	includeData = False
	pretty = False
	optlist, args = getopt.getopt(sys.argv[1:], 'cde:hijo:ptv')
	for (option, value) in optlist:
		if option == '-c':
			outputCSV = True
		if option == "-d":
			includeData = True
		if option == "-e":
			outputEncoding = value
		if option == "-h":
			header = True
		if option == "-i":
			interpretCodes = True
		if option == '-j':
			outputJSON = True
		if option == "-o":
			outputPath = value
		if option == "-p":
			pretty = True
		if option == "-t":
			outputText = True
		if option == "-v":
			printVersion = True
	if printVersion:
		print "..%s" % savJSONVersion
	if len (args) > 0:	
		(root, savExt) = os.path.splitext (args [0])
		if not savExt: savExt = ".sav"
		try:
			dataset = SAVDataset (root + savExt)
		except exceptions.Exception, e:
			print "--Cannot load SAV file '%s': %s" %\
				(root + savExt, e)
			traceback.print_exc ()
			sys.exit (0)
	else:
		print "--No SAV file specified"
		sys.exit (0)
	if dataset.SPSSVersion.startswith ("Unknown"):
		print "--Warning: Unknown SPSS version - little-endian format assumed"
	print "..SAV file encoding is %s" % dataset.originalEncoding
	print "..%d record(s) in data file" % dataset.nCases
	print "..%d variable(s) in each record" % len (dataset.varNames)
	if outputCSV:
		def interpretedCell (value, codeList):
			if codeList and codeList.get (value):
				return codeList [value]
			else:
				return blankNone (value)
		try:
			CSVFilename = os.path.join (outputPath, root + ".csv")
			f = open (CSVFilename, "wb")
			writer = unicodecsv.writer (f, encoding=outputEncoding)
			if header: writer.writerow (dataset.varNames)
			codeListList = []
			for index, variable in enumerate (dataset.variables):
				if interpretCodes:
					codeList = dataset.normalisedValueLabels.get (variable.name)
				else:
					codeList = None
				codeListList.append (codeList)					
			for record in dataset.records:
				writer.writerow([interpretedCell (col, codeListList [index]) for
					index, col in enumerate (record)])
			print "..CSV data written to %s" % f.name
			f.close ()
		except exceptions.Exception, e:
			print "--Failed to write CSV file: %s" % e
			traceback.print_exc ()

	if outputJSON:
		try:
			JSONFilename = os.path.join (outputPath, root + ".json")
			f = open (JSONFilename, "wb")
			if pretty:
				print >>f, json.dumps (dataset.toObject (),
					sort_keys=True,
					indent=4,
					separators=(',', ': ')
					)
			else:
				print >>f, json.dumps (dataset.toObject ())
			print "..JSON text written to %s" % f.name
			f.close ()
		except exceptions.Exception, e:
			print "--Failed to write JSON file: %s" % e
			traceback.print_exc ()

	if dataset.textInfo:
		print "..SAV file has %d character(s) of text information" %\
			len (savData.textInfo)
	if dataset.textInfo and outputText:
		try:
			TextFilename = os.path.join (outputPath, root + ".txt")
			f = open (JSONFilename, "w")
			print >>f, savData.textInfo
			print "..Text information written to %s" % f.name
			f.close ()
		except exceptions.Exception, e:
			print "--Failed to write text file: %s" % e
			traceback.print_exc ()
