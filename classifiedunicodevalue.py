# Classified value - data type inferred from unicode representation of value

# Types have a hierarchy of sophistication from missing to date/time.
# A variable has the type order of its value with the highest order.

import re

typeMnemonic = ["blank", "integer", "decimal", "text"]

numberRE = re.compile ("([+\-]?[0-9]+)(\.[0-9]*)?$")

# Type orders are None, Integer, Decimal, Text
isNumericTypeOrder = [False, True, True, False]

class ClassifiedUnicodeValue (object):
	def __init__ (self, text):
		self.text = text
		if self.text is not None:
			self.text = unicode (self.text).strip ()	# Original value
		else:
			self.text = ""
		self.value = None	# Value for calculation
		self.dp = None
		if len (self.text) == 0:
			self.type = None
			self.typeOrder = 0	# Type order
		else:
			numberMatch = numberRE.match (self.text)
			if numberMatch:
				whole = numberMatch.group (1)
				self.digits = len (whole)
				fraction = numberMatch.group (2)
				if fraction:
					# Treat up to 10 trailing zeroes after d.p. as integer
					if ".0000000000".startswith (fraction):
						self.typeOrder = 1
					else:
						self.typeOrder = 2
				else:
					self.typeOrder = 1
				if self.typeOrder == 1:
					self.type = int
					self.value = int (whole)
				else:
					self.type = float
					self.value = float (self.text)
					self.dp = len (numberMatch.group (2)) - 1
			else:
				self.value = self.text
				self.type = unicode
				self.typeOrder = 3
				
	def __hash__ (self):
		if self.typeOrder == 0:
			return 0
		return self.value.__hash__ ()
				
	def __cmp__ (self, other):
		if self.typeOrder != other.typeOrder:
			if isNumericTypeOrder [self.typeOrder] and\
			   isNumericTypeOrder [other.typeOrder]:
			   	return cmp (float (self.value), float (other.value))
			else:
				return cmp (self.typeOrder, other.typeOrder)
		elif  self.typeOrder == 0:
			return 0
		else:
			return cmp (self.value, other.value)
			
	def __str__ (self):
		if self.typeOrder == 0: return "blank"
		return "%s:%s" % (typeMnemonic [self.typeOrder], self.value)
		
class ClassifiedDistribution (object):
	"""
	A classified distribution is based on a frequency distribution supplied
	as a dictionary of value/frequency pairs.

	The distribution is used to infer the following properties:
		total count of items
		typeOrder: the most general typeOrder found in the values
		frequencyType:
			empty (all values missing)
			constant (all values the same)
			unique (all values different)
			id (all values unique and either integer or same length string)
			distributed (some values are repeated)
		blank frequency
		non-blank frequency
		unique frequency (number of values occuring once only)
		minimum value and frequency
		maximum value and frequency
		modal value and frequency
		collapsedDistribution: value and count of all repeated values, in
			classified Unicode value order.
	"""

	def __init__ (self, distribution):
		self.totalCount = sum (distribution.values ())
		self.nonMissingFrequency = 0
		self.missingFrequency = 0
		self.frequencyType = 'empty'
		self.dataType = 'blank'
		self.uniqueFrequency = 0
		self.uniqueValues = 0
		if self.totalCount == 0: return
		distributionVector = []
		for originalValue, count in distribution.items ():
			value = ClassifiedUnicodeValue (originalValue)
			if value.typeOrder == 0:
				self.missingFrequency += count
			else:
				distributionVector.append ((count, value))
		if len (distributionVector) == 0: return
		self.nonMissingFrequency = self.totalCount - self.missingFrequency
		distributionVector.sort (key = lambda x: x[1])	# values
		self.minimumFrequency, self.minimumValue = distributionVector [0]
		self.maximumFrequency, self.maximumValue = distributionVector [-1]
		distributionVector.sort ()	# frequency
		self.uniqueValues = len (distributionVector)
		self.modalFrequency, self.modalValue = distributionVector [-1]
		typeOrderFrequencies = {}
		self.maxTextLength = None
		self.minTextLength = None
		self.maxDigits = 0
		self.maxDP = 0
		maxTypeOrder = 0
		self.collapsedDistribution = []
		for (count, value) in distributionVector:
			maxTypeOrder = max (value.typeOrder, maxTypeOrder)
			if count > self.modalFrequency:
				self.modalValue = value
				self.modalFrequency = count
			if typeOrderFrequencies.has_key (value.typeOrder):
				typeOrderFrequencies [value.typeOrder] += 1
			else:
				typeOrderFrequencies [value.typeOrder] = 1
			if value.typeOrder in (1, 2):
				self.maxDigits = max (self.maxDigits, value.digits)
			if value.typeOrder == 2:
				self.maxDP = max (self.maxDP, value.dp)
			textLength = len (value.text)
			if self.maxTextLength is None or textLength > self.maxTextLength:
				self.maxTextLength = textLength
			if self.minTextLength is None or textLength < self.minTextLength:
				self.minTextLength = textLength
			if count == 1:
				self.uniqueFrequency += 1
			else:
				self.collapsedDistribution.append\
					((value, count))
		if self.minTextLength is None: self.minTextLength = 0
		self.collapsedDistribution.sort ()
		self.dataType = typeMnemonic [maxTypeOrder]
		if self.dataType == "text":
			commonSuffixLength = 0
			while commonSuffixLength < self.minTextLength:
				nextPrefixChar = distributionVector [0] [1].text\
					[-(commonSuffixLength + 1)]
				enlarged = False
				for count, value in distributionVector [1:]:
					if nextPrefixChar != value.text [-(commonSuffixLength + 1)]:
						break
				else:
					commonSuffixLength += 1
					enlarged = True
				if not enlarged: break
			if commonSuffixLength:
				self.commonSuffix = distributionVector [0] [1].text [-commonSuffixLength:]
			else:
				self.commonSuffix = ""
		if len (distributionVector) == 1:
			self.frequencyType = 'constant'
		elif len (distributionVector) == self.nonMissingFrequency:
			self.frequencyType = 'unique'
			if self.missingFrequency == 0 and\
			   (not typeOrderFrequencies.has_key (2)) and\
			   self.minTextLength == self.maxTextLength:
			   self.frequencyType = 'id'
		else:
			self.frequencyType = 'variable'
			
	def toObject (self, includeTotal=True):
		result = {
			"unique_values": self.uniqueValues,
			"data_type": self.dataType,
			"frequency_type": self.frequencyType,
			"missing_frequency": self.missingFrequency,
			"non_missing_frequency": self.nonMissingFrequency,
			"unique_frequency": self.uniqueFrequency
		}
		if includeTotal: result ["total_count"] = self.totalCount
		if self.frequencyType != "empty":
			result ["modal_frequency"] = self.modalFrequency
			result ["modal_value"] = self.modalValue.value
			result ["min_value"] = self.minimumValue.value
			result ["max_value"] = self.maximumValue.value
			result ["min_text_length"] = self.minTextLength
			result ["max_text_length"] = self.maxTextLength
			result ["max_digits"] = self.maxDigits
			result ["max_dp"] = self.maxDP
		if self.frequencyType == "variable":
			distribution = {}
			for value, count in self.collapsedDistribution:
				distribution [value.value] = count
			result ["distribution"] = distribution
		if self.dataType == "text" and len (self.commonSuffix):
			result ["common_suffix"] = self.commonSuffix
		return result
		
class ClassifiedUnicodeValueCache (object):
	def __init__ (self):
		self.cache = {}
	def get (self, value):
		try:
			return self.cache [value]
		except:
			result = ClassifiedUnicodeValue (value)
			self.cache [value] = result
			return result
				
if __name__ == "__main__":

	import json
	
	def prettyPrint (o):
		return json.dumps(o,
			sort_keys=True,
			indent=4,
			separators=(',', ': ')
		)
	
	print "..Testing classifiedunicodevalue module"

	print "Null distribution"
	CD1 = ClassifiedDistribution ({})
	print prettyPrint (CD1.toObject ())

	print "Only missing values"
	CD2 = ClassifiedDistribution ({None: 100})
	print prettyPrint (CD2.toObject ())

	print "Constant decimal value"
	CD3 = ClassifiedDistribution ({"111.3": 100})
	print prettyPrint (CD3.toObject ())

	print "Constant text value"
	CD4 = ClassifiedDistribution ({None: 100, "J1234": 100})
	print prettyPrint (CD4.toObject ())

	print "Unique values"
	CD5 = ClassifiedDistribution ({
		None: 100,
		101.1: 1,
		99: 1
	})
	print prettyPrint (CD5.toObject ())
	
	print "Id values"
	CD6 = ClassifiedDistribution ({
		1:1,
		'A1':1,
		'B1':1
	})
	print prettyPrint (CD6.toObject ())
	
	print "Distribution of integer values"
	CD7 = ClassifiedDistribution ({
		1:100,
		2:50,
		3:1,
		4:1
	})
	print prettyPrint (CD7.toObject ())
	
	print "Distribution of whole number real values"
	CD7 = ClassifiedDistribution ({
		1.0:100,
		2.0:50,
		3:1,
		4.1:1
	})
	print prettyPrint (CD7.toObject ())
	
	print "Distribution including zero values"
	CD7 = ClassifiedDistribution ({
		0.0:100,
		0:50,
		"":2,
		1:3
	})
	print prettyPrint (CD7.toObject ())
