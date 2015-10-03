# Tools to support JSON survey datasets

import itertools
import json
	
import classifiedunicodevalue
from classifiedunicodevalue import ClassifiedUnicodeValue
import unicodecsv
from version import savutilName, savutilVersion
		
# Use run length compression on a sequence of data values

def compressedValueSequence (s, jsonType=None):
	length = sum (1 for _ in s [1])
	value = s [0]
	if value is not None:
		if jsonType == "integer": value = int (value)
		elif jsonType == "decimal": value = float (value)
	if length == 1:
		return value
	else:
		if value is None:
			return {"n": length}
		else:
			return {
				"r": length,
				"v": value
			}

def compressedValues (values, jsonType=None):
	return [compressedValueSequence (s, jsonType)
		for s in itertools.groupby (values, lambda x: x)]
	
def valueIterator (values):
	for valueItem in values:
		if type (valueItem) == dict:
			nulls = valueItem.get ("n")
			if nulls is not None:
				for index in xrange (nulls):
					yield None
			else:
				value = valueItem.get ("v")
				for index in xrange (valueItem.get ("r")):
					yield value
		else:
			yield valueItem
