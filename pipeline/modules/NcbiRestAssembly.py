#!/usr/bin/env python

import NcbiEutils

class NcbiRestAssembly:

	def __init__(self, assembly_accession):
		self.assembly_accession = assembly_accession
		self.eutils = NcbiEutils.NcbiEutils()
		esearch_result = self.eutils.esearch_query(db='assembly', field = 'assemblyaccession', search_term=self.assembly_accession, extra_args='')
		id_list = esearch_result['esearchresult']['idlist']
		valid_ids = []
		valid_esummary_result = None
		for id in id_list:
			esummary_result = self.eutils.esummary_query(db = 'assembly', ncbi_id = id, extra_args = '')
			if esummary_result['result'][id]['assemblyaccession'] == self.assembly_accession:
				valid_ids.append(id)
				valid_esummary_result = esummary_result
		if len(valid_ids) != 1:
			exit('Cannot find unique Assembly ID for ' + self.assembly_accession + f'; IDs include {valid_ids}')
		self.summary = valid_esummary_result['result'][valid_ids[0]]

	def species(self):
		return self.summary['speciesname']

	def species_and_common_name(self):
		return self.summary['organism']

		#return self.esummarizer_analyzer.get_result().summaries[self.biosample_uid]['organism']

if __name__ == "__main__":
	main()
