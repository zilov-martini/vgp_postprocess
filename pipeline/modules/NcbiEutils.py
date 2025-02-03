import re
import sys
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
from datetime import datetime
import time
import netrc

class NcbiEutils:
	max_query_attempts = 1
	last_query_time = None
	eutils_base_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
	host_name = 'eutils.ncbi.nlm.nih.gov'

	def __init__(self, debug_mode = False):
		self.debug_mode = debug_mode

	def api_key(self):
		my_netrc = netrc.netrc()
		return my_netrc.authenticators(self.host_name)[2]

	def eutils_query(self, url_suffix):

		standard_args = '&retmode=json&api_key=' + self.api_key()
		url = self.eutils_base_url + url_suffix + standard_args

		eutils_adapter = HTTPAdapter(max_retries=self.max_query_attempts)
		eutils_session = requests.Session()
		eutils_session.mount(self.eutils_base_url, eutils_adapter)
		
		if self.debug_mode:
			print(url)

		try:
			if self.last_query_time != None:
				time_since_last_query = datetime.now() - self.last_query_time

				required_microsecond_delay = 110000			
				if time_since_last_query.days == 0 and time_since_last_query.seconds == 0 and time_since_last_query.microseconds < required_microsecond_delay:
					time.sleep((required_microsecond_delay - time_since_last_query.microseconds) / 1000000)

			self.last_query_time = datetime.now()
			req = eutils_session.get(url)

			if req.json() == None:
				exit('Failed to get JSON')

			eutils_session.close()

			return req
		except ConnectionError as ce:
			eutils_session.close()
			print(ce)

	def eutils_xml_query(self, url_suffix):

		standard_args = '&api_key=' + self.api_key()
		url = self.eutils_base_url + url_suffix + standard_args

		eutils_adapter = HTTPAdapter(max_retries=self.max_query_attempts)
		eutils_session = requests.Session()
		eutils_session.mount(self.eutils_base_url, eutils_adapter)
		
		if self.debug_mode:
			print(url)

		try:
			if self.last_query_time != None:
				time_since_last_query = datetime.now() - self.last_query_time

				required_microsecond_delay = 110000			
				if time_since_last_query.days == 0 and time_since_last_query.seconds == 0 and time_since_last_query.microseconds < required_microsecond_delay:
					time.sleep((required_microsecond_delay - time_since_last_query.microseconds) / 1000000)

			self.last_query_time = datetime.now()
			req = eutils_session.get(url)

			if req.text == None:
				exit('Failed to get JSON')

			return req
		except ConnectionError as ce:
			print(ce)


	def eutils_post_query(self, url_suffix, data):

		# Add standard arguments to data
		data['api_key'] = self.api_key(),
		data['retmode'] = 'json'

		url = self.eutils_base_url + url_suffix

		eutils_adapter = HTTPAdapter(max_retries=self.max_query_attempts)
		eutils_session = requests.Session()
		eutils_session.mount(self.eutils_base_url, eutils_adapter)
		
		if self.debug_mode:
			print(url)

		try:
			if self.last_query_time != None:
				time_since_last_query = datetime.now() - self.last_query_time

				required_microsecond_delay = 110000			
				if time_since_last_query.days == 0 and time_since_last_query.seconds == 0 and time_since_last_query.microseconds < required_microsecond_delay:
					time.sleep((required_microsecond_delay - time_since_last_query.microseconds) / 1000000)

			self.last_query_time = datetime.now()
			req = eutils_session.post(url, data)

			if req.json() == None:
				exit('Failed to get JSON')

			return req
		except ConnectionError as ce:
			print(ce)

	def esearch_query(self, db, field, search_term, extra_args):
		url_suffix = 'esearch' + '.fcgi?' + 'db=' + db + '&field=' + field + '&term=' + search_term + extra_args
		return self.eutils_query(url_suffix).json()

	def esummary_query(self, db, ncbi_id, extra_args):
		url_suffix = 'esummary' + '.fcgi?' + 'db=' + db + '&id=' + ncbi_id + extra_args
		return self.eutils_query(url_suffix).json()

	def esummary_post_query(self, db, data):
		url_suffix = 'esummary' + '.fcgi'
		data['db'] = db
		return self.eutils_post_query(url_suffix, data).json()

	def efetch_query(self, db, ncbi_id, extra_args):
		url_suffix = 'efetch' + '.fcgi?' + 'db=' + db + '&id=' + ncbi_id + extra_args
		return self.eutils_xml_query(url_suffix).text

	def database_id_for_database_accession(self, accession, database):

		search_field = 'Accession'
		if database == 'Assembly':
			search_field = 'Assembly accession'

		assembly_json = self.esearch_query(
			db = database,
			field = search_field,
			search_term = accession, 
			extra_args = '',
		)

		if 'esearchresult' in assembly_json and 'idlist' in assembly_json['esearchresult']:
			return assembly_json['esearchresult']['idlist'][0]
		else:
			print('Cannot find ID for ' + accession)
			return(None)

	def nucleotide_fasta(self, accession):
		ncbi_id = self.database_id_for_database_accession(accession, 'nuccore')
		efetch_result = self.efetch_query(
			db = 'nuccore',
			ncbi_id = ncbi_id,
			extra_args = '&rettype=fasta&retmode=text',
		)
		return(efetch_result)

class NcbiNucleotideSet:
	def __init__(self, accessions = [], eutils = None):
		self.accessions = accessions
		if eutils == None:
			self.eutils = NcbiEutils()
		else:
			self.eutils = eutils
		self._nucleotide_json = None

	@property
	def nucleotide_json(self):
		if self._nucleotide_json == None:
			self._nucleotide_json = {
				'uids': [],
			}
			# Go through in batches of 400
			#exit('Output depends on batchsize: look into it')
			batch_size = 400

			for batch_start in range(0, len(self.accessions), batch_size):
				ncbi_id_slice = self.accessions[batch_start:(batch_start+batch_size)]
				ncbi_id_slice_string = ','.join(ncbi_id_slice)
				raw_nucleotide_json = self.eutils.esummary_post_query(db='nucleotide', data={'id':ncbi_id_slice_string})
				if 'error' in  raw_nucleotide_json:
					exit('Error: ' + raw_nucleotide_json['error'])
				if 'result' in raw_nucleotide_json:
					for key in raw_nucleotide_json['result'].keys():
						if key == 'uids':
							self._nucleotide_json['uids'] = self._nucleotide_json['uids'] + raw_nucleotide_json['result']['uids']
						else:
							self._nucleotide_json[key] = raw_nucleotide_json['result'][key]						
		return self._nucleotide_json

	@property
	def uids(self):
		if self.nucleotide_json != None and 'uids' in self.nucleotide_json:
			return self.nucleotide_json['uids']
		else:
			exit('No taxid found in ' + str(self.nucleotide_json))

	def _property_for_accession(self, entry_property):
		property_for_accession = {}
		for uid in self.uids:
			if uid in self.nucleotide_json:
				if 'accessionversion' in self.nucleotide_json[uid] and entry_property in self.nucleotide_json[uid]:
					property_for_accession[self.nucleotide_json[uid]['accessionversion']] = self.nucleotide_json[uid][entry_property]
				else:
					exit('No ' + entry_property + ' found')
			else:
				exit('No ' + entry_property + ' found')
		return property_for_accession

	@property
	def taxid_for_accession(self):
		return self._property_for_accession('taxid')

	@property
	def title_for_accession(self):
		return self._property_for_accession('title')

	@property
	def organism_for_accession(self):
		return self._property_for_accession('organism')

if __name__ == "__main__":
    main()