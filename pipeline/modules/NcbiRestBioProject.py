#!/usr/bin/env python

import NcbiEutils

class NcbiRestBioProject:

	def __init__(self, bioproject_accession):
		self.bioproject_accession = bioproject_accession
		self.eutils = NcbiEutils.NcbiEutils()
		esearch_result = self.eutils.esearch_query(db='bioproject', field = 'Accession', search_term=self.bioproject_accession, extra_args='')
		id_list = esearch_result['esearchresult']['idlist']
		if len(id_list) != 1:
			exit('Cannot find unique BioProject ID for ' + self.bioproject_accession)
		esummary_result = self.eutils.esummary_query(db = 'bioproject', ncbi_id = id_list[0], extra_args = '')
		self.summary = esummary_result['result'][id_list[0]]

	def description(self):
		return self.summary['project_description']

#	def taxonomy_id(self):
#		return self.summary['taxonomy']

if __name__ == "__main__":
	main()
