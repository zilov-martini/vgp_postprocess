#!/usr/bin/env python

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
import xml.etree.ElementTree as ET

class EnaBioSample:

	browser_api_base_url = 'https://www.ebi.ac.uk/ena/browser/api/'
	max_query_attempts = 1

	def __init__(self, biosample_accession, debug_mode = False):
		self.biosample_accession = biosample_accession
		self.debug_mode = debug_mode

		raw_xml = self.ena_xml_query(self.biosample_accession)
		xml_element = ET.fromstring(raw_xml)
		if len(xml_element) != 1:
			exit('Could not obtain unique XML element')

		self.xml_element = xml_element

	def ena_xml_query(self, accession):

		data_type = 'xml'
		url = self.browser_api_base_url + data_type + '/' + accession

		ena_adapter = HTTPAdapter(max_retries=self.max_query_attempts)
		ena_session = requests.Session()
		ena_session.mount(self.browser_api_base_url, ena_adapter)
		
		if self.debug_mode:
			print(url)

		try:
			req = ena_session.get(url)

			if req.text == None:
				exit('Failed to get JSON')

			return req.text
		except ConnectionError as ce:
			print(ce)

	def species(self):
		return self.xml_element[0].find('SAMPLE_NAME').find('SCIENTIFIC_NAME').text

	def taxonomy_id(self):
		return self.xml_element[0].find('SAMPLE_NAME').find('TAXON_ID').text

if __name__ == "__main__":
	main()
