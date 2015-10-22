# Convert a CSV file into a JSON object with distribution
	
import classifiedunicodevalue
from classifiedunicodevalue import ClassifiedUnicodeValue
from datautil import compressedValueSequence, compressedValues
import unicodecsv
from version import savutilName, savutilVersion

def blankNone (x):
	if x is None:
		return u""
	else:
		return unicode (x)

def objectify (x):
	if x == "":
		return None
	else:
		try:
			i = int (x)
			return i
		except:
			try:
				f = float (x)
				return g
			except:
				return x

if __name__ == "__main__":

	import getopt
	import json
	import os
	import sys
	import xlrd

	optlist, args = getopt.getopt(sys.argv[1:], 'ad:h:s:e:o:w:')

	delimiter = ","
	headerIndex = None
	skipLines = None
	encoding = "cp1252"
	outputPath = ""
	worksheetName = None

	for (option, value) in optlist:
		if option == "-d":
			delimiter = value
		if option == "-e":
			encoding = value
		if option == "-h":
			headerIndex = int (value)
		if option == "-o":
			outputPath = value
		if option == "-s":
			skipLines = int (value)
		if option == "-w":
			worksheetName = value

	if skipLines is None:
		if headerIndex is None:
			headerIndex = 1
		skipLines = headerIndex

	if len (args) < 1 or\
	   headerIndex > skipLines:
		print "--Usage: [-d,] [-ecp1252] [-h1] [-s1] <inputFile> [<outputFile>]"
		sys.exit (0)

	(root, csvExt) = os.path.splitext (args [0])
	if not csvExt:
		if worksheetName:
			csvExt = ".xlsx"
		else:
			csvExt = ".csv"
	inputFilename = root + csvExt

	if len (args) > 1:
		outputFilename = args [1]
	else:
		outputFilename = os.path.join (outputPath, root + ".json")

	if headerIndex:
		print "..Using line %d for headers" % headerIndex
	if not (skipLines == 1 and headerIndex == 1):
		print "..Taking data from line %d onwards" % skipLines
	if worksheetName:
		print "..Looking for worksheet '%s' in workbook %s" %\
			(worksheetName, inputFilename)
		wb = xlrd.open_workbook (inputFilename)
		ws = wb.sheet_by_name (worksheetName)
		print ws.ncols, ws.nrows
		csvRows = [
			[ws.cell_value (rowx, colx) for colx in xrange (ws.ncols)]
			for rowx in xrange (ws.nrows)
		]
	else:
		csvFile = open (inputFilename)
		csv = unicodecsv.UnicodeReader (csvFile, encoding=encoding, delimiter=delimiter)
		csvRows = list (csv)
		csvFile.close ()
	if skipLines > len (csvRows):
		print "--Only %d row(s) found in CSV file, %d required for header" %\
			(len (csvRows), skipLines)
		sys.exit (0)
	if headerIndex:
		headers = csvRows [headerIndex-1]
		csvRows = csvRows [skipLines:]
	print "..%d row(s) found in input" % len (csvRows)

	jsonObject = {
		"origin": "csv2json %s from %s" % 
			(savutilVersion, inputFilename),
		"code_lists": {},
		"variable_sequence": headers,
		"total_count": len (csvRows),
		"variables": {},
		"data": {}
	}
	variables = jsonObject ["variables"]
	data = jsonObject ["data"]
	for index, variableName in enumerate (headers):
		values = [ClassifiedUnicodeValue (row [index]).value for row in csvRows]
		distribution = {}
		for value in values:
			if distribution.has_key (value):
				distribution [value] += 1
			else:
				distribution [value] = 1
		cd = classifiedunicodevalue.ClassifiedDistribution (distribution)
		if cd.dataType == "integer":
			jsonType = "integer"
		elif cd.dataType == "decimal":
			jsonType = "decimal"
		elif cd.dataType == "text":
			jsonType = "string"
		else:
			jsonType = "null"		
		variables [variableName] = {
			"sequence": index + 1,
			"name": variableName,
			"json_type": jsonType,
			"distribution": cd.toObject (includeTotal=False)
		}
		data [variableName] = compressedValues (values, jsonType)

	jsonFile = open (outputFilename, 'wb')
	json.dump (jsonObject, jsonFile,
		sort_keys=True,
		indent=4,
		separators=(',', ': ')
	)
	jsonFile.close ()
