import re
import sys
import pymysql
import collections
import requests
import json
import urllib
import warnings
import NcbiEutils
import xml.etree.ElementTree as ET

class Taxonomy:
	taxonomy_data_dir = '/nfs/compgen-03/jt8/data_staging/taxdmp/'
	debug_mode = False

	def __init__(self, query_name, scientific_name = False, genus_fallback = False):
		self.query_name = query_name
		self.ncbi_taxonomy_db = pymysql.connect(host='gritdb', user='gritro', port=3419, db='jt8_ncbi_taxonomy')
		self.ncbi_taxonomy_cursor = self.ncbi_taxonomy_db.cursor()
		self.scientific_name = scientific_name
		self.genus_fallback = genus_fallback
		self.genus = False
		self.eutils = NcbiEutils.NcbiEutils()
		self.tax_id = self.tax_id_for_query_name()

	def can_fall_back_to_genus(self):
		if self.genus_fallback and re.search('\s', self.query_name):
			return True
		else:
			return False

	def fall_back_to_genus(self):
		warnings.warn('Falling back to genus')
		self.query_name = re.split('\s+', self.query_name)[0]
		self.genus = True

	def tax_id_for_query_name(self):
		tax_id = None
		if self.scientific_name:
			tax_id = self.tax_id_for_scientific_query_name()
		else:
			tax_id = self.tax_id_for_unscientific_query_name()
		if tax_id == None and self.can_fall_back_to_genus():
			self.fall_back_to_genus()
			return self.tax_id_for_query_name()
		return tax_id

	def tax_id_for_unscientific_query_name(self):
		if self.ncbi_taxonomy_cursor.execute('SELECT tax_id FROM name WHERE name_txt = %s', self.query_name):
			tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return tax_id_query_results[0][0]
		else:
			warnings.warn('Cannot find tax id for ' + self.query_name)
			return None

	def tax_id_for_scientific_query_name(self):
		if self.ncbi_taxonomy_cursor.execute('SELECT tax_id FROM name WHERE name_class = \'scientific name\' and name_txt = %s', self.query_name):
			tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return tax_id_query_results[0][0]
		else:
			warnings.warn('Cannot find tax id for ' + self.query_name)
			return None

	def genbank_hidden_flag(self):
		if self.ncbi_taxonomy_cursor.execute('SELECT GenBank_hidden_flag FROM node WHERE tax_id = \'' + str(self.tax_id) + '\''):
			tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return tax_id_query_results[0][0]
		else:
			exit('Cannot find parent tax id for ' + self.tax_id)

	def parent_for_tax_id(self, tax_id):
		if self.ncbi_taxonomy_cursor.execute('SELECT parent_tax_id FROM node WHERE tax_id = \'' + str(tax_id) + '\''):
			tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return tax_id_query_results[0][0]
		else:
			exit('Cannot find parent tax id for ' + tax_id)

	def rank_for_tax_id(self, tax_id):
		if self.ncbi_taxonomy_cursor.execute('SELECT rank FROM node WHERE tax_id = \'' + str(tax_id) + '\''):
			tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return tax_id_query_results[0][0]
		else:
			exit('Cannot find rank for ' + tax_id)

	def name_for_tax_id(self, tax_id):
		if self.ncbi_taxonomy_cursor.execute('SELECT name_txt FROM name WHERE name_class = \'scientific name\' and tax_id = \'' + str(tax_id) + '\''):
			tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return tax_id_query_results[0][0]
		else:
			print('WARNING: Cannot find name for ' + str(tax_id))
			return None

	def common_name_for_tax_id(self, tax_id):
		if self.ncbi_taxonomy_cursor.execute('SELECT name_txt FROM name WHERE name_class = \'genbank common name\' and tax_id = \'' + str(tax_id) + '\''):
			common_name_results = self.ncbi_taxonomy_cursor.fetchall()
			return common_name_results[0][0]
		else:
			return None

	def display_name_for_rank(self):
		name_for_rank = self.get_name_for_rank()
		for rank in name_for_rank:
			print("{0:<15s}{1}".format(rank, name_for_rank[rank]))

	def display_names_and_ranks(self):
		names_and_ranks = self.get_names_and_ranks()
		for name_and_rank in names_and_ranks:
			print("{0:<15s}{1}".format(name_and_rank['RANK'], name_and_rank['NAME']))

	def display_names_and_ranks_with_genome_count(self):
		names_and_ranks = self.get_names_and_ranks()
		for name_and_rank in names_and_ranks:
			print("{0:<15s}{1:<25s}{2}".format(name_and_rank['RANK'], name_and_rank['NAME'], self.genome_count_for_tax_id(name_and_rank['TAX_ID'])))

	def genome_count_for_tax_id(self, tax_id):
		eutils_utility = 'esearch'
		efetch_standard_args = '&rettype=count&retmode=json'

		db = 'Genome'
		field = 'Organism'
		search_term = 'txid' + str(tax_id)
		json = self.eutils.esearch_query(db, field, search_term, efetch_standard_args)

		return int(json['esearchresult']['count'])

	def chromosome_level_assembly_ids_for_tax_id(self, tax_id):
		eutils_utility = 'esearch'
		efetch_standard_args = '&retmode=json'

		json_1 = self.eutils.esearch_query(
			db = 'Assembly', 
			field = 'Organism', 
			search_term = 'txid' + str(tax_id),
			extra_args = '&usehistory=y'
		)

		json_2 = self.eutils.esearch_query(
			db = 'Assembly', 
			field = 'Assembly Level', 
			search_term = 'Chromosome', 
			extra_args = '&query_key=' + json_1['esearchresult']['querykey'] + '&WebEnv=' + json_1['esearchresult']['webenv'] + '&retmax=1000',
		)

		assembly_ids = []
		if 'idlist' in json_2['esearchresult']:
			assembly_ids = json_2['esearchresult']['idlist']

		return assembly_ids

	def details_for_assembly_id(self, assembly_id):
		assembly_json = self.eutils.esummary_query(
			db = 'Assembly', 
			ncbi_id = assembly_id, 
			extra_args = '',
		)
		accession = None
		if 'latestaccession' in assembly_json['result'][assembly_id] and assembly_json['result'][assembly_id]['latestaccession'] != '':
			accession = assembly_json['result'][assembly_id]['latestaccession']
		else:
			accession = assembly_json['result'][assembly_id]['assemblyaccession']

		return({
			'accession': accession,
			'organism': assembly_json['result'][assembly_id]['organism'],
			'submissiondate': assembly_json['result'][assembly_id]['submissiondate'],
			'scaffoldn50': assembly_json['result'][assembly_id]['scaffoldn50'],
			'contign50': assembly_json['result'][assembly_id]['contign50'],
		})

	def get_name_for_rank(self):
		names_and_ranks = self.get_names_and_ranks()

		name_for_rank = collections.OrderedDict()

		for name_and_rank in names_and_ranks:
			if name_and_rank['RANK'] != 'no rank':
				name_for_rank[name_and_rank['RANK']] = name_and_rank['NAME']

		return name_for_rank

	def get_common_name(self):
		return self.common_name_for_tax_id(self.tax_id)

	def get_names_and_ranks(self):
		#print(self.query_name)

		names_and_ranks = []

		current_tax_id = self.tax_id

		while current_tax_id != None and self.name_for_tax_id(current_tax_id) != 'root' and self.name_for_tax_id(current_tax_id) != 'all':
			parent_tax_id = self.parent_for_tax_id(current_tax_id)
			rank = self.rank_for_tax_id(current_tax_id)
#			print("\tRANK:" + rank)

			name_for_tax_id = self.name_for_tax_id(current_tax_id)
			if name_for_tax_id == None:
				name_for_tax_id = 'None'

			names_and_ranks.append({
				'NAME': name_for_tax_id,
				'RANK': rank,
				'TAX_ID': current_tax_id,				
			})

			current_tax_id = self.parent_for_tax_id(current_tax_id)

		return names_and_ranks

	def lowest_common_ranked_name_and_rank(self, other_taxonomy):
		my_name_for_rank = self.get_name_for_rank()
		other_name_for_rank = other_taxonomy.get_name_for_rank()
		
		for rank in my_name_for_rank:
			if rank in other_name_for_rank and other_name_for_rank[rank] == my_name_for_rank[rank]:
				return([my_name_for_rank[rank], rank])

		exit('Could not find common relationship')

	def lowest_common_name_and_rank(self, other_taxonomy):
		my_names_and_ranks = self.get_names_and_ranks()
		other_names_and_ranks = other_taxonomy.get_names_and_ranks()
		
		for my_name_and_rank in my_names_and_ranks:
			for other_name_and_rank in other_names_and_ranks:
				if other_name_and_rank['TAX_ID'] == my_name_and_rank['TAX_ID']:
					return(my_name_and_rank)

		exit('Could not find common relationship')

	def closest_chromosome_level_assemblies(self):
		for name_and_rank in self.get_names_and_ranks():
			assembly_ids = self.chromosome_level_assembly_ids_for_tax_id(name_and_rank['TAX_ID'])
			if len(assembly_ids) > 0:
				details_for_accession = {}
				for assembly_id in assembly_ids:
					details_for_assembly = self.details_for_assembly_id(assembly_id)
					details_for_accession[details_for_assembly['accession']] = details_for_assembly

				print("{0} (taxonomic rank {1}, {2} assemblies)".format(name_and_rank['NAME'], name_and_rank['RANK'], len(details_for_accession)))
				for assembly_accession in details_for_accession:
					print("\t{0} {1}, date {2}, contig N50 {3:.0f} kb, scaff N50 {4:.0f} kb".format(details_for_accession[assembly_accession]['organism'], assembly_accession, re.sub(' \d\d\:\d\d$', '', details_for_accession[assembly_accession]['submissiondate']), details_for_accession[assembly_accession]['contign50']/1000, details_for_accession[assembly_accession]['scaffoldn50']/1000))
				break

	def _get_child_tax_ids_and_rank_for_tax_id_list(self, tax_ids):
		tax_id_string = ','.join(list(map(lambda x: str(x), tax_ids)))
		#print('select tax_id, rank from node where parent_tax_id in (' + tax_id_string + ')')
		if self.ncbi_taxonomy_cursor.execute('select tax_id, rank from node where parent_tax_id in (' + tax_id_string + ')'):
			child_tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return child_tax_id_query_results
		else:
			return([])

	def _get_classified_child_tax_ids_and_rank_for_tax_id_list(self, tax_ids):
		tax_id_string = ','.join(list(map(lambda x: str(x), tax_ids)))
		#print('select tax_id, rank from node where parent_tax_id in (' + tax_id_string + ')')
		if self.ncbi_taxonomy_cursor.execute('select distinct NO.tax_id, NO.rank from node NO, name NA where NO.tax_id=NA.tax_id AND NA.name_txt not like \'%unclassified%\' AND NO.parent_tax_id in (' + tax_id_string + ')'):
			child_tax_id_query_results = self.ncbi_taxonomy_cursor.fetchall()
			return child_tax_id_query_results
		else:
			return([])

	# Just get species
	def get_child_species_tax_ids(self, tax_id, classified=False):
		leaf_ids = []
		parent_tax_ids = [tax_id]
		child_tax_ids_and_ranks = []
		if classified:
			child_tax_ids_and_ranks = self._get_classified_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)
		else:
			child_tax_ids_and_ranks = self._get_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)

		while len(child_tax_ids_and_ranks) > 0:
			parent_tax_ids = []
			for row in child_tax_ids_and_ranks:
				parent_tax_ids.append(row[0])
				if row[1] == 'species':
					leaf_ids.append(row[0])
			if classified:
				child_tax_ids_and_ranks = self._get_classified_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)
			else:
				child_tax_ids_and_ranks = self._get_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)

		return leaf_ids

	# Just get species and subspecies
	def get_child_species_and_subspecies_tax_ids(self, tax_id):
		leaf_ids = []
		parent_tax_ids = [tax_id]
		child_tax_ids_and_ranks = self._get_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)
		while len(child_tax_ids_and_ranks) > 0:
			parent_tax_ids = []
			for row in child_tax_ids_and_ranks:
				parent_tax_ids.append(row[0])
				if row[1] == 'species' or row[1] == 'subspecies':
					leaf_ids.append(row[0])
			child_tax_ids_and_ranks = self._get_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)

		return leaf_ids

	# Get every child tax ID, including those above species level
	def get_child_tax_ids(self, tax_id):
		leaf_ids = []
		parent_tax_ids = [tax_id]
		child_tax_ids_and_ranks = self._get_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)
		while len(child_tax_ids_and_ranks) > 0:
			parent_tax_ids = []
			for row in child_tax_ids_and_ranks:
				parent_tax_ids.append(row[0])
				leaf_ids.append(row[0])
			child_tax_ids_and_ranks = self._get_child_tax_ids_and_rank_for_tax_id_list(parent_tax_ids)

		return leaf_ids


#Proc to give two lists: the things that got a result, and the things that didn’t.
#SELECT 
#ALSO get the rank, using a join if neededselect tax_id, parent_tax_id from node where parent_tax_id in ([LIST]);assign child_taxa_found_for hash to 1for each query_taxon in query_taxa:	if query_taxon not in child_taxa_found_for:		leaf_taxa.append(query_taxon)
#ALSO check if anything is a species or subspecies
#FURTHER SEARCH all new taxa, recursivelyRETURN all leaf taxa and also all species and subspecies


class OttTaxonomy(Taxonomy):

	def __init__(self, query_name, scientific_name = False, genus_fallback = False):
		self.query_name = query_name
		self.scientific_name = scientific_name
		self.genus_fallback = genus_fallback
		self.genus = False

	def tax_id_for_query_name(self):
		ott_base_url = 'https://api.opentreeoflife.org/v3/'
		url_suffix = 'tnrs/match_names'
		url = ott_base_url + url_suffix
		data = {'names': [self.query_name]}
		tax_id_response = requests.post(url, headers={'content-type': 'application/json'}, data = json.dumps(data))
		tax_id_json = tax_id_response.json()
		
		if self.debug_mode:
			print(url)
			print(tax_id_response)
			print(tax_id_json)
	
		if ('results' in tax_id_json
			and len(tax_id_json['results']) == 1
			and 'matches' in tax_id_json['results'][0]
			and len(tax_id_json['results'][0]['matches']) == 1
			and 'taxon' in tax_id_json['results'][0]['matches'][0]
			and 'ott_id' in tax_id_json['results'][0]['matches'][0]['taxon']):
			
			return int(tax_id_json['results'][0]['matches'][0]['taxon']['ott_id'])
		else:
			warnings.warn('Cannot find tax id for ' + self.query_name)
			return None

	def get_names_and_ranks(self):
		ott_base_url = 'https://api.opentreeoflife.org/v3/'
		url_suffix = 'tree_of_life/node_info' #YOU MAY WISH TO SEE WHAT DIFFERENT RESULTS "TAXON INFO" PRODUCES
		
		tax_id = self.tax_id
		if tax_id == None:
			return []

		url = ott_base_url + url_suffix
		data = {'ott_id': tax_id, 'include_lineage': True}
		name_and_rank_response = requests.post(url, headers={'content-type': 'application/json'}, data = json.dumps(data))
		name_and_rank_json = name_and_rank_response.json()
		
		if self.debug_mode:
			print(url)
			print(name_and_rank_response)
			print(name_and_rank_json)

		names_and_ranks = []
		if 'taxon' in name_and_rank_json and 'lineage' in name_and_rank_json:
			# First append the current taxon, then go up the lineage
			names_and_ranks.append({
				'NAME': name_and_rank_json['taxon']['name'],
				'RANK': name_and_rank_json['taxon']['rank'],
				'TAX_ID': name_and_rank_json['taxon']['ott_id']
			})
				
			for taxon in name_and_rank_json['lineage']:
				if 'taxon' in taxon:
					names_and_ranks.append({
						'NAME': taxon['taxon']['name'],
						'RANK': taxon['taxon']['rank'],
						'TAX_ID': taxon['taxon']['ott_id']
					})
		else:
			warnings.warn('Cannot find lineage for ' + self.query_name)
			return []

		return names_and_ranks

	# TEMPORARY HACK!
	def common_name_for_tax_id(self, tax_id):
		return None

	pass

class EutilsTaxonomy(Taxonomy):

	def tax_id_for_query_name(self):
		tax_id_json = self.eutils.esearch_query(
			db = 'taxonomy',
			field = 'All Names',
			search_term = self.query_name,
			extra_args = '',
		)
		if 'esearchresult' in tax_id_json and 'idlist' in tax_id_json['esearchresult'] and len(tax_id_json['esearchresult']['idlist']) == 1:
			return int(tax_id_json['esearchresult']['idlist'][0])
		else:
			warnings.warn('Cannot find tax id for ' + self.query_name)
			return None

	def get_taxonomy_xml(self):
		taxonomy_xml = self.eutils.efetch_query(
			db = 'taxonomy',
			ncbi_id = str(self.tax_id),
			extra_args = 'retmode=xml&rettype=xml',
		)

		if self.debug_mode:
			print(taxonomy_xml)

		return taxonomy_xml

	def get_names_and_ranks(self):
		taxonomy_xml_root = ET.fromstring(self.get_taxonomy_xml())
		taxon = taxonomy_xml_root.find('Taxon')
		lineage = taxon.find('LineageEx')

		names_and_ranks = []
		names_and_ranks.append({
			'NAME': taxon.find('ScientificName').text,
			'RANK': taxon.find('Rank').text,
			'TAX_ID': taxon.find('TaxId').text,
		})

		for lineage_taxon in reversed(lineage):
			names_and_ranks.append({
				'NAME': lineage_taxon.find('ScientificName').text,
				'RANK': lineage_taxon.find('Rank').text,
				'TAX_ID': lineage_taxon.find('TaxId').text,
			})
		return names_and_ranks

	def get_species_and_authority(self):
		taxonomy_xml_root = ET.fromstring(self.get_taxonomy_xml())
		taxon = taxonomy_xml_root.find('Taxon')
		dispname = taxon.find('OtherNames').find('Name').find('DispName').text

		return dispname

	pass

class WormsTaxonomy(Taxonomy):
	
	def __init__(self, query_name, scientific_name = False, genus_fallback = False):
		self.query_name = query_name
		self.scientific_name = scientific_name
		self.genus_fallback = genus_fallback
		self.genus = False
	
	def tax_id_for_query_name(self):
		ott_base_url = 'http://www.marinespecies.org/rest/'
		url_suffix = 'AphiaIDByName/'
		url = ott_base_url + url_suffix
		data = {'names': [self.query_name]}
		tax_id_response = requests.post(url, headers={'content-type': 'application/json'}, data = json.dumps(data))
		tax_id_json = tax_id_response.json()
		
		if self.debug_mode:
			print(url)
			print(tax_id_response)
			print(tax_id_json)
		
		if ('results' in tax_id_json
			and len(tax_id_json['results']) == 1
			and 'matches' in tax_id_json['results'][0]
			and len(tax_id_json['results'][0]['matches']) == 1
			and 'taxon' in tax_id_json['results'][0]['matches'][0]
			and 'ott_id' in tax_id_json['results'][0]['matches'][0]['taxon']):
			
			return int(tax_id_json['results'][0]['matches'][0]['taxon']['ott_id'])
		else:
			warnings.warn('Cannot find tax id for ' + self.query_name)
			return None

	def get_names_and_ranks(self, tax_id):
		ott_base_url = 'https://api.opentreeoflife.org/v3/'
		url_suffix = 'tree_of_life/node_info' #YOU MAY WISH TO SEE WHAT DIFFERENT RESULTS "TAXON INFO" PRODUCES
		
		url = ott_base_url + url_suffix
		data = {'ott_id': tax_id, 'include_lineage': True}
		name_and_rank_response = requests.post(url, headers={'content-type': 'application/json'}, data = json.dumps(data))
		name_and_rank_json = name_and_rank_response.json()
		
		if self.debug_mode:
			print(url)
			print(name_and_rank_response)
			print(name_and_rank_json)
	
		names_and_ranks = []
		if 'taxon' in name_and_rank_json and 'lineage' in name_and_rank_json:
			# First append the current taxon, then go up the lineage
			names_and_ranks.append({
				'NAME': name_and_rank_json['taxon']['name'],
				'RANK': name_and_rank_json['taxon']['rank'],
				'TAX_ID': name_and_rank_json['taxon']['ott_id']
			})
				
			for taxon in name_and_rank_json['lineage']:
				if 'taxon' in taxon:
					names_and_ranks.append({
						'NAME': taxon['taxon']['name'],
						'RANK': taxon['taxon']['rank'],
						'TAX_ID': taxon['taxon']['ott_id']
					})
		else:
			warnings.warn('Cannot find tax id for ' + self.query_name)
			return None
	
		return names_and_ranks

pass

class UsiTaxonomy(Taxonomy):

	def __init__(self, query_name, scientific_name = False, genus_fallback = False):
		self.query_name = query_name
		self.scientific_name = scientific_name
		self.genus_fallback = genus_fallback
		self.rest_base_url = 'https://species-ws.nbnatlas.org/'
		self.genus = False

	def tax_id_for_query_name(self):
		url_suffix = 'search?q=scientificName:'
		url = self.rest_base_url + url_suffix + self.query_name

		if self.genus:
			url += '&fq=rank:genus'
		else:
			url += '&fq=rank:species'

		tax_id_response = requests.get(url)
		tax_id_json = tax_id_response.json()
		
		if self.debug_mode:
			print(url)
			print(tax_id_response)
			print(tax_id_json)
	
		if 'searchResults' in tax_id_json:
			for result_json in tax_id_json['searchResults']['results']:
				if 'scientificName' in result_json and result_json['scientificName'] == self.query_name:
					return result_json['guid']

		warnings.warn('Cannot find tax id for ' + self.query_name)

		# Fall back to a genus-level search
		if self.can_fall_back_to_genus():
			self.fall_back_to_genus()
			return self.tax_id
		else:
			return None

	def get_names_and_ranks(self):
		url_suffix = 'classification/'

		tax_id = self.tax_id
		if tax_id == None:
			return []

		url = self.rest_base_url + url_suffix + tax_id
		name_and_rank_response = requests.get(url)
		name_and_rank_json = name_and_rank_response.json()
		
		if self.debug_mode:
			print(url)
			print(name_and_rank_response)
			print(name_and_rank_json)

		names_and_ranks = []
		if len(name_and_rank_json) > 0:
			for taxon in reversed(name_and_rank_json):
				if 'scientificName' in taxon:
					names_and_ranks.append({
						'NAME': taxon['scientificName'],
						'RANK': taxon['rank'],
						'TAX_ID': taxon['guid']
					})
		else:
			warnings.warn('Cannot find lineage for ' + self.query_name)
			return []

		return names_and_ranks

	def common_name_for_tax_id(self, tax_id):
		url_suffix = 'species/'

		if tax_id == None:
			return None

		url = self.rest_base_url + url_suffix + tax_id
		common_name_response = requests.get(url)
		common_name_json = common_name_response.json()

		if 'commonNames' in common_name_json:
			for common_name in common_name_json['commonNames']:
				if common_name['status'] == 'preferred':
					return common_name['nameString']

		return None

	pass

class GoatTaxonomy(Taxonomy):

	def __init__(self, query_name, scientific_name = False, genus_fallback = False, tax_id=None, test=False):

		# Fix formatting issues
		self.query_name = query_name[0].upper() + query_name[1:].lower()
		self.query_name = re.sub('‘', "'", self.query_name) 
		self.query_name = re.sub('’', "'", self.query_name)
		self.query_name = re.sub('(et al.?) (\d{4})', r"\1 (\2)", self.query_name)

		self.scientific_name = scientific_name
		self.genus_fallback = genus_fallback
		self.rest_base_url = 'https://goat.genomehubs.org/api/v0.0.1/'
		self.eutils = NcbiEutils.NcbiEutils()
		self.genus = False
		self.test = test
		if tax_id == None:
			self.tax_id = self.tax_id_for_query_name()
		else:
			self.tax_id = int(tax_id)
		self._json = None

	@property
	def json(self):
		if self._json == None:

			url_suffix= 'record?result=taxon&taxonomy=ncbi&recordId='
			query_for_url = str(self.tax_id)
			url = self.rest_base_url + url_suffix + query_for_url

			if self.test:
				print(url)

			tax_id_response = requests.get(url)
			if 'status' in tax_id_response.json() and tax_id_response.json()['status']['hits'] == 1:
				self._json = tax_id_response.json()['records'][0]['record']

			if self.debug_mode:
				print(url)
				print(tax_id_response)
				print(tax_id_json)
		return self._json	

	def tax_id_for_query_name(self):
		tax_id = None
		url_suffix = 'search?result=taxon&includeEstimates=true&offset=0&size=10000&query='
		query = f'tax_tree({self.query_name})'
		query_for_url = urllib.parse.quote(query, safe='')
		url = self.rest_base_url + url_suffix + query_for_url
		if self.test:
			print(url)
		search_response = requests.get(url)
		tax_ids_for_class = {}
		for result in search_response.json()['results']:
			for taxon_name in result['result']['taxon_names']:
				if taxon_name['name'].lower() == self.query_name.lower() and taxon_name['class'] in ['scientific name', 'scientifc name', 'equivalent name','synonym','includes'] and re.match('^\d+$', result['result']['taxon_id']):
					if taxon_name['class'] not in tax_ids_for_class:
						tax_ids_for_class[taxon_name['class']] = []
					tax_ids_for_class[taxon_name['class']].append(result['result']['taxon_id'])
					# break

		# Assign tax-ID, preferring ones based on scientific name over synoynms
		for name_class in ['scientific name', 'scientifc name', 'equivalent name','synonym','includes']:
			if name_class in tax_ids_for_class:
				if len(tax_ids_for_class[name_class]) != 1:
					exit(f"Cannot obtain unique taxonomy result: duplicates. {tax_ids_for_class[name_class]}")
				tax_id = int(tax_ids_for_class[name_class][0])
				break

		# If that did't find anything, report problems and fall back to genus
		if tax_id == None:
			warnings.warn('Cannot find tax id for ' + self.query_name)

			# Fall back to a genus-level search
			if self.can_fall_back_to_genus() and self.genus == False:
				self._json = None
				self.fall_back_to_genus()
				return self.tax_id_for_query_name()
			else:
				return None

		self.tax_id = tax_id
		return self.tax_id

	def get_names_and_ranks(self):
		names_and_ranks = []
		if 'lineage' in self.json:
			for taxon in self.json['lineage']:
				if 'scientific_name' in taxon:
					names_and_ranks.append({
						'NAME': taxon['scientific_name'],
						'RANK': taxon['taxon_rank'],
						'TAX_ID': taxon['taxon_id']
					})
		else:
			warnings.warn('Cannot find lineage for ' + self.query_name)
			return []

		return names_and_ranks

	# Get every child tax ID, including those above species level
	def get_child_tax_ids(self):
		url_suffix = 'search?result=taxon&fields=none&size=1000000&taxonomy=ncbi&query='
		query = f'tax_tree({self.tax_id})'
		if self.tax_id == None:
			query = f'tax_tree({self.query_name})'

		query_for_url = urllib.parse.quote(query, safe='')
		url = self.rest_base_url + url_suffix + query_for_url

		tax_id_response = requests.get(url, headers={"accept":"text/tab-separated-values"})
		tax_id_response_lines = re.split('\n', tax_id_response.text)

		child_tax_ids = []
		for tax_id_response_line in tax_id_response_lines:
			fields = re.split('\t', tax_id_response_line)
			if re.match('^\d+$', fields[0]):
				child_tax_ids.append(fields[0])

#		child_tax_ids = []
#		if 'status' in tax_id_response.json() and tax_id_response.json()['status']['hits'] > 0:
#			for result in tax_id_response.json()['results']:
#				if re.match('^\d+$', result['result']['taxon_id']):
#					child_tax_ids.append(result['result']['taxon_id'])
#		else:
#			exit('Could not obtain child tax IDs')

		return child_tax_ids

	pass


if __name__ == "__main__":
	main()
