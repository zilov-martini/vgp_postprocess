import requests
import netrc
import json
import subprocess
import re
import os
import yaml
import Taxonomy
import tempfile
import GritJiraQuery
import GritJiraAuth
from Bio import SeqIO
import gzip
from datetime import datetime

class GritJiraIssue:

	host_name = "jira.sanger.ac.uk"
	base_url = 'https://jira.sanger.ac.uk/'

	rest_extension = 'rest/api/2/'
	attachment_scratch_dir = '/lustre/scratch123/tol/teams/grit/jt8/contamination_screen//jira_attachment_scratch/'
	tol_dir = '/lustre/scratch124/tol/projects/'
	scratch122_dir = '/lustre/scratch122/tol/data/'
	old_tol_dir = '/lustre/scratch116/tol/projects/'
	grit_dir = '/lustre/scratch123/tol/teams/grit/geval_pipeline/grit_rawdata/'

	proxies = {
		'http': 'http://wwwcache.sanger.ac.uk:3128',
		'https': 'http://webcache.sanger.ac.uk:3128',
	}

	id_for_custom_field_name = {
		'version': 11625,
		'sample_id': 11627, 
		'assembly_type': 11624, 
		'contamination_files': 11677,
		'datatype_available': 11660,
		'important': 11678,
		'accession_data': 11631, 
		'gEVAL_database': 11643,
		'species_name': 11676,
		'chromosome_naming': 11607,
		'manual_breaks': 11615,
		'manual_joins': 11681,
		'manual_inversions': 11610,
		'manual_haplotig_removals': 11632,
		'data_copied': 11671,
		'assembly_statistics': 11608,
		'metadata_files': 11658,
		'submission_date': 11628,
		'chromosome_result': 11645,
		'curator': 11657,
		'released_to': 11656,
		'release_version': 11609,
		'hic_kit': 11629,
		'karyotype': 11605,
		'submission_note': 11674,
		'genome_note': 11614,
		'synteny_source': 11622,
		'release_to': 11649,
		'gfastats': 11648,
		'assembled_by': 11668,
		'expected_sex': 11641,
		'contamination': 12802,
		'treeval': 12200,
		'hap2_chromosome_result': 13109,
		'hap2_gfastats': 13111,
		'hap2_assembly_statistics': 13110,
		'yaml': 13408,
	} 

	taxon_for_sample_prefix = {
		'a': 'amphibians',
		'b': 'birds',
		'c': 'non-vascular-plants',
		'd': 'dicots',
		'e': 'echinoderms',
		'f': 'fish',
		'g': 'fungi',
		'h': 'platyhelminths',
		'i': 'insects',
		'j': 'jellyfish',
		'k': 'chordates', # Might change to "other-chordates"
		'l': 'monocots',
		'm': 'mammals',
		'n': 'nematodes',
		'o': 'sponges',
		'p': 'protists',
		'q': 'arthropods',
		'r': 'reptiles',
		's': 'sharks',
		't': 'other-animal-phyla',	
		'u': 'algae',
		'v': 'vascular-plants', # Might change to "other-vascular-plants"
		'w': 'annelids',
		'x': 'molluscs',
		'y': 'bacteria',
		'z': 'archea',
	}

	contamination_screen_clade_for_sample_prefix = {
		'a': 'chordata',
		'b': 'chordata',
		'c': 'viridiplantae',
		'd': 'viridiplantae',
		'e': 'other_metazoa',
		'f': 'chordata',
		'g': 'fungi',
		'h': 'other_metazoa',
		'i': 'arthropoda',
		'j': 'other_metazoa',
		'k': 'chordata',
		'l': 'viridiplantae',
		'm': 'chordata',
		'n': 'other_metazoa',
		'o': 'other_metazoa',
		'p': 'other_eukaryota',
		'q': 'arthropoda',
		'r': 'chordata',
		's': 'chordata',
		't': 'other_metazoa',	
		'u': 'other_eukaryota',
		'v': 'viridiplantae',
		'w': 'other_metazoa',
		'x': 'other_metazoa',
		'y': 'bacteria',
		'z': 'archea',
	}

	required_software = {
		'hifi_assemblers': ['hifiasm', 'hicanu', 'falcon-unzip','metamdbg','hifiasm-meta','flye'],
		'hic_assemblers': ['salsa', 'yahs','instagraal'],
	}

	optional_software = {
		'aligners': ['longranger'],
		'polishers': ['freebayes'],
		'mito_assemblers': ['mitohifi', 'mbg','mitos webserver', 'oatk','tiara', 'mitos'],
		'haplotig_purgers': ['purge_dups', 'bbtools dedupe'],
		'decontamination': ['blobtoolkit'],
		'marker_pipeline': ['markerscan'],
	}

	internal_projects = [
		'Darwin',
		'VGP',
		'ASG',
		'ERGA',
		'TOL',
		'BGE',
		'Psyche',
		'AEGIS',
	]

	metagenome_projects = [
		'Darwin',
		'ASG',
		'ERGA',
	]

	high_priority_projects = [
		'ASG',
		'BGE',
		'ERGA',
		'AEGIS',
	]

	slack_notification_projects = [
		'Darwin',
		'ASG',
		'TOL',
		'BGE',
		'Psyche',
	]

	def __init__(self, key = None, creation_data = None, tolid = None, species = None):
		self.debug_mode = False
		self._issue_json = None
		self._yaml = None
		self._assembly_name = None
		self._taxonomy = None
		self._yaml_mode = 'FILE'

		if key != None and creation_data == None:
			self.key = key
		elif key == None and creation_data != None:
			self.create_issue(creation_data)
		elif tolid != None:
			grit_jira_query = GritJiraQuery.GritJiraQuery()
			issue_keys = grit_jira_query.get_issue_keys_for_tolid(tolid)
			if len(issue_keys) != 1:
				exit(f'Cannot identify unique ticket for TOLID {tolid}')
			self.key = issue_keys[0]
		elif species != None:
			grit_jira_query = GritJiraQuery.GritJiraQuery()
			issue_keys = grit_jira_query.get_issue_keys_for_species(species)
			if len(issue_keys) != 1:
				exit(f'Cannot identify unique ticket for species {species}: {issue_keys}')
			self.key = issue_keys[0]
		else:
			exit('Invalid ticket constructor setup')

		if key != None and re.match(r'^CR', key) and not self.is_yaml_available():
			self._yaml_mode = 'ATTACHMENT'

	def create_assembly_dir(self):
		assembly_dir = self.get_assembly_draft_version_dir()

		if not os.path.isdir(assembly_dir):
			directory_creation_script = '~mm49/workspace/tol-it/storage/dirstruct/dirstruct_tol_prod'
			underscore_species = re.sub(r'\s+', '_', self.get_species())
			os.system(f'{directory_creation_script} genomeark {self.get_directory_taxon()} {underscore_species}')
			os.mkdir(self.get_assembly_draft_version_dir())

	def requests_get(self, url):

		my_netrc = netrc.netrc()

#		response = requests.get(url, auth=(my_netrc.authenticators(self.host_name)[0], my_netrc.authenticators(self.host_name)[2]), proxies=self.proxies)
		response = requests.get(url, auth=GritJiraAuth.GritJiraAuth(my_netrc.authenticators(self.host_name)[0], my_netrc.authenticators(self.host_name)[2]), proxies=self.proxies)

		if self.debug_mode == True:
			print(url)
			print(response)

		if not response.ok:
			exit(f'HTTP request for {url} failed: ' + response.reason)

		return response

	def requests_delete(self, url):

		my_netrc = netrc.netrc()
		response = requests.delete(url, auth=GritJiraAuth.GritJiraAuth(my_netrc.authenticators(self.host_name)[0],my_netrc.authenticators(self.host_name)[2]), proxies=self.proxies)

		if self.debug_mode == True:
			print(url)
			print(response)

		if not response.ok:
			exit('HTTP request failed: ' + response.reason)

		return response

	def rest_get(self, url):
		return self.requests_get(url).json()

	def rest_put(self, url, data_to_put, post=False):

		if self.debug_mode == True:
			print(url)

		my_netrc = netrc.netrc()
		response = None
		if post:
			response = requests.post(url, headers={'content-type': 'application/json'}, auth=GritJiraAuth.GritJiraAuth(my_netrc.authenticators(self.host_name)[0],my_netrc.authenticators(self.host_name)[2]), data = json.dumps(data_to_put), proxies=self.proxies)
		else:
			response = requests.put(url, headers={'content-type': 'application/json'}, auth=GritJiraAuth.GritJiraAuth(my_netrc.authenticators(self.host_name)[0],my_netrc.authenticators(self.host_name)[2]), data = json.dumps(data_to_put),proxies=self.proxies)

		if response.status_code == 204:
			return
		elif response.status_code == 201:
			return response.json()
		else:
			exit('Failed to update JIRA: ' + str(response.status_code) + ' ' + str(response.json()))

	def jira_put(self, jira_method, data_to_put, post=False):
		url = self.base_url + self.rest_extension + jira_method
		result_json = self.rest_put(url, data_to_put, post=post)
		return result_json

	@property
	def issue_json(self):
		if self._issue_json == None:
			jira_method = 'issue/'
			query_data = self.key
			url = self.base_url + self.rest_extension + jira_method + query_data
			self._issue_json = self.rest_get(url)
		return self._issue_json

	def refresh_issue_json(self):
		self._issue_json = None

	def is_yaml_available(self):
		if self._yaml_mode == 'FILE':
			return self.custom_field_has_content('yaml')
		elif self._yaml_mode == 'ATTACHMENT':
			if self.get_yaml_attachment_url() != None:
				return True
			else:
				return False
		else:
			return False

	def get_yaml_attachment_url(self):
		yaml_attachments = []
		for attachment_url in self.get_attachment_urls():
			if re.search(r'\.y(a)?ml$', attachment_url) and not re.search('treeval', attachment_url.lower()):
				yaml_attachments.append(attachment_url)
		
		if len(yaml_attachments) != 1:
			print(f'Cannot identify unique YAML attachment; attachments include {yaml_attachments}')
			return None
		else:
			return yaml_attachments[0]

	@property
	def yaml(self):
		if self._yaml_mode == 'FILE':
			return self.yaml_from_file()
		elif self._yaml_mode == 'ATTACHMENT':
			return self.yaml_from_attachment()
		else:
			exit('Non-standard YAML mode')
		
	def reload_yaml(self):
		self._yaml = None

	def yaml_from_file(self):
		if self._yaml == None:

			if self.get_custom_field('yaml') == None or not os.path.isfile(self.get_custom_field('yaml')):
				exit(f'Cannot load YAML for {self.key}')

			yaml_text = None
			with open(self.get_custom_field('yaml'), 'r') as yaml_handle:
				yaml_text = yaml_handle.read()

			yaml_dict = yaml.safe_load(yaml_text)
			self._yaml = yaml_dict
		return self._yaml

	# This is not normally needed
	def locate_yaml_file(self):
		if os.path.isdir(self.get_assembly_draft_version_dir()):
			potential_yaml_files = [x for x in os.listdir(self.get_assembly_draft_version_dir()) if re.search(r'\.ya?ml$', x)]
			if len(potential_yaml_files) == 1:
				return self.get_assembly_draft_version_dir() + potential_yaml_files[0]
			else:
				print(f'Cannot locate YAML file. Candidates include {potential_yaml_files}')
				return None
		else:
			return None

	# This is not normally used
	def yaml_from_attachment(self):
		if self._yaml == None:
			if self.get_yaml_attachment_url() == None:
				exit(f'Cannot load YAML for {self.key}')

			yaml_text = self.requests_get(self.get_yaml_attachment_url())
			yaml_dict = yaml.safe_load(yaml_text.content)
			self._yaml = yaml_dict
		return self._yaml

	def write_yaml_attachment_to_file(self, yaml_filename):
		if self.get_yaml_attachment_url() == None:
			exit(f'Cannot load YAML for {self.key}')
	
		self.create_assembly_dir()

		yaml_handle = open(yaml_filename, 'w')
		yaml.dump(self.yaml, yaml_handle) 
		yaml_handle.close()

	def yaml_key_has_content(self,key):
		if key in self.yaml and self.yaml[key] != None and (self.yaml[key] == True or not re.match(r'^\s*$', str(self.yaml[key]))):
			return True
		else:
			return False
		
	def custom_field_has_content(self, custom_field_name):
		if self.get_custom_field(custom_field_name) != None and (self.get_custom_field(custom_field_name) == True or not re.match(r'^\s*$', str(self.get_custom_field(custom_field_name)))):
			return True
		else:
			return False

	def yaml_key_is_true(self,key):
		if key in self.yaml and self.yaml[key] != None and (self.yaml[key] == True or re.match('true', self.yaml[key].lower())):
			return True
		else:
			return False

	def yaml_has_taxid(self):
		if self.yaml_key_has_content('taxid') and re.match(r'^\d+\S*$', self.yaml['taxid']):
			return True
		else:
			return False

	def modify_local_yaml(self, key, value):
		# Make sure the YAML has been downloaded
		current_yaml = self.yaml

		self._yaml[key] = value

	def replace_yaml_file(self):
		# Generate new local YAML file
#		temp_dir = tempfile.TemporaryDirectory()
	
		yaml_handle = open(self.get_custom_field('yaml'), 'w')
		yaml.dump(self.yaml, yaml_handle)    # Write a YAML representation of data to 'document.yaml'.
		yaml_handle.close()

#		self.replace_yaml_with_file(temp_yaml_filename)

#		temp_dir.cleanup()

	# Replace YAML with named file
	def replace_yaml_with_file(self, yaml_filename):
		# Generate new local YAML file
	
		# Remove old YAML
		attachment_id_urls = [
			attachment['self']
			for attachment
			in self.issue_json['fields']['attachment']
			if re.search(r'\.y(a)?ml$', attachment['content'])
		]

		if len(attachment_id_urls) == 0:
			exit('Cannot identify existing YAML')

		for attachment_id_url in attachment_id_urls:
			self.requests_delete(attachment_id_url)

		# Upload new YAML file
		self.add_attachment(yaml_filename)

	@property
	def taxonomy(self):
		if self._taxonomy == None:
			if self.is_yaml_available() and 'taxonomy_id' in self.yaml:
				self._taxonomy = Taxonomy.GoatTaxonomy(self.get_species(), scientific_name = True, genus_fallback = True, tax_id = self.yaml['taxonomy_id'])
			else:
				self._taxonomy = Taxonomy.GoatTaxonomy(self.get_species(), scientific_name = True, genus_fallback = True)
		return self._taxonomy

	def get_mito_assembly(self):
		# The YAML isn't consistent for this, hence this method
		if 'mito' in self.yaml:
			return self.get_local_assembly_for_label('mito')
		elif 'mt' in self.yaml:
			return self.get_local_assembly_for_label('mt')
		else:
			print('No mito assembly in YAML')
			return None

	def get_plastid_assembly(self):
		if 'plastid' in self.yaml:
			return self.get_local_assembly_for_label('plastid')
		else:
			print('No plastid assembly in YAML')
			return None

	def get_contamination_screen_clade_from_sample_id(self):
		sample_prefix = self.get_custom_field('sample_id')[0]
		if sample_prefix in self.contamination_screen_clade_for_sample_prefix:
			return self.contamination_screen_clade_for_sample_prefix[sample_prefix]
		else:
			return None

	def get_phylum_from_species(self):
		names_and_ranks = self.taxonomy.get_names_and_ranks()
		for name_and_rank in names_and_ranks:
			if name_and_rank['RANK'] == 'phylum':
				return name_and_rank['NAME']
		exit('Could not find phylum')

	def get_tol_group_from_species(self):
		names_and_ranks = self.taxonomy.get_names_and_ranks()

		classification_for_tol_group_by_priority = [
			{
				'amphibians': {'rank': 'class', 'name': 'Amphibia'},
				'birds': {'rank': 'class', 'name': 'Aves'},
				'dicots': {'rank': 'clade', 'name': 'eudicotyledons'},
				'echinoderms': {'rank': 'phylum', 'name': 'Echinodermata'},
				'fish': {'rank': 'superclass', 'name': 'Actinopterygii'},
				'fungi': {'rank': 'kingdom', 'name': 'Fungi'},
				'platyhelminths':  {'rank': 'phylum', 'name': 'Platyhelminthes'},
				'insects': {'rank': 'class', 'name': 'Insecta'},
				'jellyfish': {'rank': 'phylum', 'name': 'Cnidaria'},
				'monocots': {'rank': 'clade', 'name': 'Liliopsida'},
				'mammals': {'rank': 'class', 'name': 'Mammalia'},
				'nematodes': {'rank': 'phylum', 'name': 'Nematoda'},
				'sponges': {'rank': 'phylum', 'name': 'Porifera'},
				'sharks': {'rank': 'class', 'name': 'Chondrichthyes'},
				'annelids': {'rank': 'phylum', 'name': 'Annelida'},
				'molluscs': {'rank': 'phylum', 'name': 'Mollusca'},
				'bacteria': {'rank': 'superkingdom', 'name': 'Bacteria'},
				'archea': {'rank': 'superkingdom', 'name': 'Archaea'},
			},
			{
				'fish': {'rank': 'family', 'name': 'Coelacanthidae'},
			},
			{
				'fish': {'rank': 'subclass', 'name': 'Dipnomorpha'},
			},
			{
				'arthropods': {'rank': 'phylum', 'name': 'Arthropoda'}, # BUT NOT ANY OF THE OTHERS
			},
			{
				'reptiles': {'rank': 'clade', 'name': 'Amniota'}, # BUT NOT ANY OF THE OTHERS
			},
			{
				'chordates': {'rank': 'phylum', 'name': 'Chordata'}, # BUT NOT ANY OF THE OTHERS
			},
			{
				'other-animal-phyla': {'rank': 'kingdom', 'name': 'Metazoa'}, # BUT NOT ANY OF THE OTHERS
			},
		]

		tol_groups = set()
		for classification_for_tol_group in classification_for_tol_group_by_priority:
			if len(tol_groups) == 0:
				for tol_group in classification_for_tol_group:
					for name_and_rank in names_and_ranks:
						if classification_for_tol_group[tol_group]['rank'] == name_and_rank['RANK'] and classification_for_tol_group[tol_group]['name'] == name_and_rank['NAME']:
							tol_groups.add(tol_group)

		if len(tol_groups) == 0:
			taxon_list_for_tol_group = {
				'dicots': ['Buxales', 'Ranunculales'],
				'non-vascular-plants': ['Andreaeopsida', 'Andreaeobryopsida', 'Bryopsida', 'Chlorokybophyceae', 'Oedipodiopsida', 'Polytrichopsida', 'Takakiopsida', 'Tetraphidopsida', 'Haplomitriopsida', 'Jungermanniopsida', 'Marchantiopsida', 'Anthocerotopsida', 'Leiosporocerotopsida', 'Sphagnopsida'],
				'protists': ['Amoebozoa', 'Breviatea', 'Dictyostelea', 'Discosea', 'Evosea', 'Tubulinea', 'Bigyra', 'Cercozoa', 'Endomyxa', 'Imbricatea', 'Euglenozoa', 'Foraminifera', 'Globothalamea', 'Phoronida', 'Ciliophora', 'Choanoflagellata', 'Choanozoa', 'Mycetozoa', 'Percolozoa', 'Rotifera', 'Sarcomastigophora', 'Acantharea', 'Actinophryidae', 'Aurearenophyceae', 'Bigyra', 'Bolidophyceae', 'Filasterea', 'Fornicata', 'Haptista', 'Heterolobosea', 'Hyphochytriomycetes', 'Ichthyosporea', 'Katablepharidophyta', 'Labyrinthulomycetes', 'Parabasalia', 'Phaeothamniophyceae', 'Picozoa', 'Placididea', 'Polycystinea', 'Preaxostyla', 'Raphidophyceae', 'Rhodelphea', 'unspecified_phylum_Protozoa', 'Chromerida', 'Colponemidia', 'Perkinsozoa', 'Apicomplexa', 'Myzozoa','Dinophyceae'],
				'algae': ['Chlorophyta', 'Cryptophyta' , 'Cryptophyceae' , 'Glaucophyta', 'Haptophyta', 'Charophyta', 'Bacillariophyceae', 'Bolidophyceae', 'Chrysomerophyceae', 'Chrysophyceae', 'Chrysophyceae', 'Dictyochophyceae', 'Eustigmatophyceae', 'Ochrophyta', 'Pelagophyceae', 'Phaeophyceae', 'Phaeophyceae', 'Pinguiophyceae', 'Synurophyceae', 'Xanthophyceae', 'Rhodophyta','Rhodomonas', 'Synchromophyceae',],
				'vascular-plants': ['Equisetopsida', 'Ginkgoopsida', 'Lycopodiopsida', 'Polypodiopsida', 'Cycadopsida', 'Gnetopsida', 'Pinopsida', 'Psilotopsida',],
			}
			for tol_group in taxon_list_for_tol_group:
				for taxon in taxon_list_for_tol_group[tol_group]:
					for name_and_rank in names_and_ranks:
						if taxon == name_and_rank['NAME']:
							tol_groups.add(tol_group)

		if len(tol_groups) != 1:
			exit(f'Cannot identify unique TOL group for {self.get_species()} from groups: {tol_groups}')

		return tol_groups.pop()

	def get_sample_prefix_for_taxon(self, taxon):
		sample_prefix_for_taxon = {}
		for sample_prefix in self.taxon_for_sample_prefix:
			sample_prefix_for_taxon[self.taxon_for_sample_prefix[sample_prefix]] = sample_prefix
		if taxon in sample_prefix_for_taxon:
			return sample_prefix_for_taxon[taxon]
		else:
			exit('Non-standard taxon: ' + taxon)

	def get_contamination_screen_clade_from_species(self):
		tol_group = self.get_tol_group_from_species()
		sample_prefix = self.get_sample_prefix_for_taxon(tol_group)
		return self.contamination_screen_clade_for_sample_prefix[sample_prefix]

	def get_attachment_urls(self):
		return [ attachment['content'] for attachment in self.issue_json['fields']['attachment'] ]

	def create_issue(self, issue_data):
		jira_method = 'issue/'

		result_json = self.jira_put(jira_method, issue_data, post=True)
		self.key = result_json['key']

	def add_attachment(self, attachment_file):
		my_netrc = netrc.netrc()
		files = {'file': open(attachment_file,'rb')}
		jira_method = 'issue/' + self.key + '/attachments/'
		add_attachment_url = self.base_url + self.rest_extension + jira_method
		response = requests.post(add_attachment_url, headers={'X-Atlassian-Token': 'no-check'}, auth=GritJiraAuth.GritJiraAuth(my_netrc.authenticators(self.host_name)[0],my_netrc.authenticators(self.host_name)[2]), files=files, proxies=self.proxies)
		files['file'].close()
		return response

	def download_attachment(self, attachment_url, destination_dir = None):
		if destination_dir == None:
			destination_dir = self.attachment_scratch_dir
		attachment_response = self.requests_get(attachment_url)
		attachment_name = attachment_url.rsplit('/', 1)[1]
		attachment_scratch_file = destination_dir + attachment_name
		attachment_handle = open(attachment_scratch_file, 'wb')
		attachment_handle.write(attachment_response.content)
		attachment_handle.close()
		return(attachment_scratch_file)

	def fetch_pretext_files(self, destination_dir = None):
		if destination_dir == None:
			destination_dir = self.get_curated_tolid_dir()
		
		pretext_dir = '/nfs/treeoflife-01/teams/grit/data/curated_pretext_maps/' + self.get_sample_prefix_for_taxon(self.get_tol_group_from_species()) + '_' + self.get_tol_group_from_species() + '/'

		tolid_pretext_filenames = []
		tolid_pretext_dirpaths = []

		for dirpath, dirnames, pretext_filenames in os.walk(pretext_dir):
			for pretext_filename in pretext_filenames:
				for haplotype_specific_assembly_name in self.get_haplotype_specific_assembly_names():
					if re.match(f'{haplotype_specific_assembly_name}' + r'.*\.pretext', pretext_filename):
						tolid_pretext_filenames.append(pretext_filename)
						tolid_pretext_dirpaths.append(dirpath)
		if len(tolid_pretext_filenames) != len(self.get_haplotype_specific_assembly_names()):
			exit(f'Cannot find unique Pretext file matching {self.get_haplotype_specific_assembly_names()[0]}.*\\.pretext in {pretext_dir}; list includes {tolid_pretext_filenames}')

		# print(f'{tolid_pretext_dirpaths[0]}/{tolid_pretext_filenames[0]}')

		for tolid_pretext_filename in tolid_pretext_filenames:
			os.system(f'cp {tolid_pretext_dirpaths[0]}/{tolid_pretext_filename} {destination_dir}')

		full_filenames = [f'{destination_dir}/{x}' for x in tolid_pretext_filenames]

		return(full_filenames)

	def download_pretext_image(self, destination_dir = None):
		if destination_dir == None:
			destination_dir = self.get_curated_tolid_dir()

		for attachment_url in self.get_attachment_urls():
			if re.search(r'cur.*\.png$', attachment_url):
				self.download_attachment(attachment_url, destination_dir)

	def generate_pretext_images(self, pretext_files, destination_dir = None):
		if destination_dir == None:
			destination_dir = self.get_curated_tolid_dir()
			
			for pretext_file in pretext_files:
				# Don't create a file if the output already exists, including in gzipped form
				(pretext_basename_stem, pretext_basename_extension) = os.path.splitext( os.path.basename(pretext_file) )
				output_file = f'{destination_dir}/{pretext_basename_stem}_FullMap.png'

				if not os.path.isfile(output_file) and not os.path.isfile(f'{output_file}.gz'):
					pretext_snapshot = 'PretextSnapshot'
					command = f'{pretext_snapshot} -m  {pretext_file} --sequences "=full" -c 26 -r 2160 -o {destination_dir}'
					print(command)
					command_result = os.system(command)
					if command_result != 0:
						exit('Failed to convert Pretext files to images')

	def resolve(self, resolution_name='Done'):
		jira_method = 'issue/' + self.key + '/transitions'	

		resolve_transition_id_for_project = {
			'CR': 761,
			'GRIT': 411,
			'RC': 411,
			'DS': 411,
		}

		if self.get_project() not in resolve_transition_id_for_project:
			exit('Cannot resolve tickets from project ' + self.get_project())

		self.transition(resolve_transition_id_for_project[self.get_project()], resolution_name)

	def transition(self, transition_id, resolution = None):
		jira_method = 'issue/' + self.key + '/transitions'

		transition_data = {
			"transition": {
				"id": transition_id,
			}
		}

		if resolution != None:
			transition_data['fields'] = {
				"resolution" : {
					"name": resolution,
				},
			}
	
		self.jira_put(jira_method, transition_data, post=True)		

	def transition_open_to_decontamination(self):
		open_to_decontamination_transition_id_for_project = {
			'RC': 501,
			'GRIT': 231,
			'DS': 11,
		}

		if self.get_project() not in open_to_decontamination_transition_id_for_project:
			exit('Cannot transition tickets from project ' + self.get_project())

		if self.get_status() == 'Open':
			self.transition(open_to_decontamination_transition_id_for_project[self.get_project()])

	def transition_past_decontamination(self):
		end_decontamination_transition_id_for_project = {
			'RC': 481,
			'GRIT': 571,
		}

		if self.get_project() not in end_decontamination_transition_id_for_project:
			exit('Cannot transition tickets from project ' + self.get_project())

		if self.get_status() == 'Decontamination':
			self.transition(end_decontamination_transition_id_for_project[self.get_project()])


	def get_summary(self):
		return self.issue_json['fields']['summary']

	def get_custom_field(self, custom_field_name):
		if custom_field_name in self.id_for_custom_field_name:
			custom_field_contents = self.issue_json['fields']['customfield_' + str(self.id_for_custom_field_name[custom_field_name])]
			if type(custom_field_contents) is dict:
				custom_field_contents = custom_field_contents['value']
			if custom_field_name == 'contamination_files' and custom_field_contents != None:
				custom_field_contents = self.correct_old_assembly_paths(custom_field_contents)
			return custom_field_contents

	@classmethod
	def get_id_for_custom_field_name(cls, custom_field_name):
		if custom_field_name in cls.id_for_custom_field_name:
			return 'customfield_' + str(cls.id_for_custom_field_name[custom_field_name])
		else:
			exit(f'Cannot find custom field for {custom_field_name}')

	def display_all_custom_fields(self):
		for custom_field_name in self.id_for_custom_field_name:
			print(custom_field_name + ':', self.issue_json['fields']['customfield_' + str(self.id_for_custom_field_name[custom_field_name])])

	def display_all_json_fields(self):
		for field_name in self.issue_json['fields']:
			print(field_name + ':', self.issue_json['fields'][field_name])

	def set_custom_field(self, custom_field_name, value):
		if custom_field_name in self.id_for_custom_field_name:
			self.set_field('customfield_' + str(self.id_for_custom_field_name[custom_field_name]), value)
		else:
			exit('Cannot identify custom field for ' + custom_field_name)

	def get_issue_type(self):
		return(self.issue_json['fields']['issuetype']['name'])

	# Get a list even if the field is a single value
	def get_list_from_yaml_key(self, yaml_key):
		list_from_yaml_key = []
		if type(self.yaml[yaml_key]) == list:
			list_from_yaml_key = self.yaml[yaml_key]
		else:
			list_from_yaml_key = [self.yaml[yaml_key]]
		return list_from_yaml_key

	def get_project_list_from_yaml(self):
		# Return None if not available
		if not self.is_yaml_available() or 'projects' not in self.yaml or len(self.yaml['projects']) == 0:
			return None
		project_list = []
		yaml_projects = self.get_list_from_yaml_key('projects')

		for yaml_project in yaml_projects:
			project = yaml_project.title()
			if re.match(r'vgp.*orders', project, re.IGNORECASE) or re.match(r'^vgp$', project, re.IGNORECASE):
				project = 'VGP'
			if re.match(r'vgp\+', project, re.IGNORECASE):
				project = 'VGP+'
			if re.match(r'CCGP', project, re.IGNORECASE):
				project = 'CCGP'
			else: # Correct capitalisation for any known internal project
				for internal_project in self.internal_projects:
					if re.match(internal_project, project, re.IGNORECASE):
						project = internal_project

			project_list.append(project)
		return project_list

	def get_curator(self):
		curator_username = self.get_custom_field('curator')
		return(self.full_name_for_username(curator_username))

	def get_curator_email(self):
		if self.get_custom_field('curator') == None:
			return None
		else:
			return self.get_custom_field('curator') + '@sanger.ac.uk'

	def get_submitter_email(self):
		return self.issue_json["fields"]["reporter"]["emailAddress"]

	def get_accessions_as_dict(self):
		accession_dict = {
		}

		if self.get_custom_field('accession_data') == None:
			return {}

		for accession_line in re.split(r'\n', self.get_custom_field('accession_data')):
			fields = re.split(r'\s*\|\s*', accession_line)
			assembly = None
			if re.search(self.get_custom_field('sample_id'), fields[0]):
				if re.search(r'alternate', fields[0]):
					assembly = 'alternate'
				elif re.search(r'\.hap1\.', fields[0]):
					assembly = 'hap1'
				elif re.search(r'\.hap2\.', fields[0]):
					assembly = 'hap2'
				else:
					assembly = 'primary'

				if assembly not in accession_dict:
					accession_dict[assembly] = {}

				for field in fields:
					if re.match(r'^(GCA_|ERZ\d+$)', field):
						accession_dict[assembly]['Assembly'] = field
					elif re.match(r'^PRJEB', field):
						accession_dict[assembly]['BioProject'] = field
		return accession_dict

	def get_primary_bioproject(self):
		accession_dict = self.get_accessions_as_dict()
		if 'primary' in accession_dict and 'BioProject' in accession_dict['primary']:
			return accession_dict['primary']['BioProject']
		else:
			return None

	def get_bioproject_for_haplotype(self, haplotype):
		accession_dict = self.get_accessions_as_dict()
		if haplotype in accession_dict and 'BioProject' in accession_dict[haplotype]:
			return accession_dict[haplotype]['BioProject']
		else:
			return None

	def get_primary_assembly(self):
		accession_dict = self.get_accessions_as_dict()
		if 'primary' in accession_dict and 'Assembly' in accession_dict['primary']:
			return accession_dict['primary']['Assembly']
		else:
			return None

	def get_alternate_bioproject(self):
		accession_dict = self.get_accessions_as_dict()
		if 'alternate' in accession_dict and 'BioProject' in accession_dict['alternate']:
			return accession_dict['alternate']['BioProject']
		else:
			return None

	def get_chromosome_naming(self):
		curator_username = self.get_custom_field('chromosome_naming')

	def get_plain_text_description(self):
		return re.sub(r'\{.*?\}', '', self.issue_json["fields"]["description"])

	def get_status(self):
		# Reset JSON for issue so that status is guaranteed to be current
		self._issue_json = None
		return self.issue_json["fields"]["status"]["name"]

	def get_pipeline_software(self):
		pipeline_steps = []
		for pipeline_entry in self.yaml['pipeline']:
			# Is it in the possible elements?
			pipeline_steps.append(re.sub(r'\s*\(.*$', '', pipeline_entry).lower())
		return pipeline_steps

	def get_software_type_for_permitted_software(self):
		permitted_software = {}
		for software_dict in (self.required_software, self.optional_software):
			for software_type in software_dict:
				for software in software_dict[software_type]:
					permitted_software[software] = software_type
		return permitted_software

	def get_pipeline_software_types(self):
		pipeline_software_type_available = {}
		
		for pipeline_software in self.get_pipeline_software():
			if pipeline_software in self.get_software_type_for_permitted_software():
				pipeline_software_type_available[self.get_software_type_for_permitted_software()[pipeline_software]] = True
			else:
				exit(f'Software {pipeline_software} not permitted')
		return pipeline_software_type_available.keys()

	def is_standard_darwin_pipeline(self):
		if not self.is_yaml_available():
			return False
		else:
			software_type_for_required_software = {}
			for software_type in self.required_software:
				for software in self.required_software[software_type]:
					software_type_for_required_software[software] = software_type

			permitted_software = []
			for software_category in [self.required_software, self.optional_software]:
				for software_type in software_category:
					for software in software_category[software_type]:
						permitted_software.append(software)

			is_standard_darwin_pipeline = True

			required_software_present = {}

			for pipeline_software in self.get_pipeline_software():
				# Is it in the possible elements?
				if pipeline_software not in permitted_software:
					is_standard_darwin_pipeline = False
				# Track whether each required element is present
				if pipeline_software in software_type_for_required_software:
					required_software_present[software_type_for_required_software[pipeline_software]] = True

			# Are all the required elements present?
			for software_type in self.required_software:
				if software_type not in required_software_present or required_software_present[software_type] != True:
					is_standard_darwin_pipeline = False

			return is_standard_darwin_pipeline

	def get_assembler(self):
		if not self.is_yaml_available():
			return self.get_assembler_from_description()
		else:
			return self.get_assembler_from_yaml()

	def get_hic_assembler(self):
		if not self.is_yaml_available():
			return self.get_hic_assembler_from_description()
		else:
			return self.get_hic_assembler_from_yaml()

	def get_assembler_from_yaml(self):

		assemblers = [
			'Hifiasm',
			'Hifiasm-Meta',
			'HiCanu',
			'Falcon-unzip',
			'metaMDBG',
			'Flye',
		]

		assembler_mentioned = {}
		for assembler in assemblers:
			for pipeline_entry in self.yaml['pipeline']:
				assembler_match = re.search(assembler, pipeline_entry, re.IGNORECASE)
				if assembler_match:
					assembler_mentioned[assembler] = 1
					if assembler == 'Hifiasm-Meta' and 'Hifiasm' in assembler_mentioned:
						assembler_mentioned.pop('Hifiasm', None)

		if len(assembler_mentioned.keys()) == 1:
			return list(assembler_mentioned.keys())[0]
		else:
			exit('Cannot find unique assembler for ' + self.key + ': ' + str(len(assembler_mentioned.keys())) + ' assemblers found')
			return None

	def get_hic_assembler_from_yaml(self):

		assemblers = [
			'SALSA',
			'YaHS',
			'instaGRAAL',
		]

		assembler_mentioned = {}
		for assembler in assemblers:
			for pipeline_entry in self.yaml['pipeline']:
				assembler_match = re.search(assembler, pipeline_entry, re.IGNORECASE)
				if assembler_match:
					assembler_to_report = assembler
					if assembler == 'SALSA':
						assembler_to_report = 'SALSA2'
					assembler_mentioned[assembler_to_report] = 1

		if len(assembler_mentioned.keys()) == 1:
			return list(assembler_mentioned.keys())[0]
		else:
			exit('Cannot find unique HiC assembler for ' + self.key + ': ' + str(len(assembler_mentioned.keys())) + ' assemblers found')
			return None

	def get_organelle_assemblers_from_yaml(self):

		assemblers = [
			'MitoHiFi',
			'MBG',
			'OATK',
			'MITOS WebServer',
			'Mitos',
			'Tiara',
		]

		assembler_mentioned = {}
		for assembler in assemblers:
			for pipeline_entry in self.yaml['pipeline']:
				assembler_match = re.search(assembler, pipeline_entry, re.IGNORECASE)
				if assembler_match:
					assembler_to_report = assembler
					assembler_mentioned[assembler_to_report] = 1

		if len(assembler_mentioned.keys()) == 1:
			return list(assembler_mentioned.keys())[0]
		elif len(assembler_mentioned.keys()) > 1:
			return ' and '.join(sorted(list(assembler_mentioned.keys())))
		else:
			# exit('Cannot find unique organelle assembler for ' + self.key + ': ' + str(len(assembler_mentioned.keys())) + ' assemblers found')
			return None

	def get_marker_pipeline_from_yaml(self):

		assemblers = [
			'MarkerScan',
		]

		assembler_mentioned = {}
		for assembler in assemblers:
			for pipeline_entry in self.yaml['pipeline']:
				assembler_match = re.search(assembler, pipeline_entry, re.IGNORECASE)
				if assembler_match:
					assembler_to_report = assembler
					assembler_mentioned[assembler_to_report] = 1

		if len(assembler_mentioned.keys()) == 1:
			return list(assembler_mentioned.keys())[0]
		elif len(assembler_mentioned.keys()) > 1:
			return ' and '.join(sorted(list(assembler_mentioned.keys())))
		else:
			# exit('Cannot find unique organelle assembler for ' + self.key + ': ' + str(len(assembler_mentioned.keys())) + ' assemblers found')
			return None

	def get_assembler_from_description(self): # This should only be used as a fallback if YAML is not available

		assemblers = [
			'Hifiasm',
			'HiCanu',
			'Falcon-unzip',
		]

		assembler_mentioned = {}
		for assembler in assemblers:
			assembler_match = re.search(assembler + r'\s\(', self.get_plain_text_description(), re.IGNORECASE)
			if assembler_match:
				assembler_mentioned[assembler] = 1

		if len(assembler_mentioned.keys()) == 1:
			return list(assembler_mentioned.keys())[0]
		else:
			exit('Cannot find unique assembler for ' + self.key + ': ' + str(len(assembler_mentioned.keys())) + ' assemblers found')
			return None

	def get_hic_assembler_from_description(self): # This should only be used as a fallback if YAML is not available

		assemblers = [
			'SALSA',
			'YaHS',
		]

		assembler_mentioned = {}
		for assembler in assemblers:
			assembler_match = re.search(assembler + r'\s\(', self.get_plain_text_description(), re.IGNORECASE)
			if assembler_match:
				assembler_mentioned[assembler] = 1

		if len(assembler_mentioned.keys()) == 1:
			return list(assembler_mentioned.keys())[0]
		else:
			exit('Cannot find unique assembler for ' + self.key + ': ' + str(len(assembler_mentioned.keys())) + ' assemblers found')
			return None

	def get_species(self):
		if re.match('^CR', self.key):
			return(self.yaml['species'])

		species_and_common_name = self.get_custom_field('species_name')
		species_match = re.match(r'(\S+\s+\S+(?:\s+\S+)*)\s+\((.*)\)', species_and_common_name)
		if species_match:
			species_name = species_match.group(1)
			species_name = re.sub(r'^(\S+)_(\S+)', r'\1 \2', species_name)
			return(species_name)
		else:
			exit('Non-standard species name in ticket: ' + species_and_common_name)

	def get_datatypes_available(self):
		datatype_available_json = self.get_custom_field('datatype_available')
		datatypes_available = []
		for element in datatype_available_json:
			datatypes_available.append(element['value'])
		return datatypes_available

	def get_release_version(self):
		return str(int(self.get_custom_field('release_version')))

	def set_assembly_name(self, assembly_name):
		self._assembly_name = assembly_name

	def get_assembly_name(self):
		if self._assembly_name == None:
			self._assembly_name = self.get_custom_field('sample_id') + '.' + self.haplotype_clause() + self.get_release_version()
		return self._assembly_name

	def get_assembly_name_for_cr_ticket(self):
		return self.yaml['specimen'] + '.' + self.haplotype_clause() + '1'

	def get_assembly_name_without_haplotype(self):
		assembly_name = self.get_custom_field('sample_id') + '.' + self.get_release_version()
		return assembly_name

	def get_assembly_name_for_haplotype(self, haplotype):
		if haplotype == None or haplotype == 'primary':
			return self.get_custom_field('sample_id') + '.' + self.get_release_version()
		else:
			return self.get_custom_field('sample_id') + '.' + haplotype + '.' + self.get_release_version()

	def get_haplotype_specific_assembly_names(self):
		haplotype_specific_assembly_names = []
		if len(self.get_haplotypes()) > 0:
			for haplotype in self.get_haplotypes():
				haplotype_specific_assembly_names.append(self.get_assembly_name_for_haplotype(haplotype))
		else:
			haplotype_specific_assembly_names = [self.get_assembly_name()]
		return haplotype_specific_assembly_names

#	def get_preferred_haplotype_assembly_name(self):
#		if len(self.get_haplotypes()) > 0:
#				haplotype = None
#				if 'hap1' in self.get_haplotypes():
#					haplotype = 'hap1'
#				elif 'maternal' in self.get_haplotypes():
#					haplotype = 'maternal'
#
#				if haplotype == None:
#					exit('Cannot determine preferred haplotype')
#				preferred_haplotype_assembly_name = self.get_assembly_name_for_haplotype(haplotype)
#		else:
#			preferred_haplotype_assembly_name = self.get_assembly_name()
#		return preferred_haplotype_assembly_name

#	def get_non_preferred_haplotype_assembly_name(self):
#		if len(self.get_haplotypes()) > 0:
#				haplotype = None
#				if 'hap2' in self.get_haplotypes():
#					haplotype = 'hap2'
#				elif 'paternal' in self.get_haplotypes():
#					haplotype = 'paternal'
#
#				if haplotype == None:
#				non_preferred_haplotype_assembly_name = self.get_assembly_name_for_haplotype(haplotype)
#					exit('Cannot determine preferred haplotype')
#		else:
#			non_preferred_haplotype_assembly_name = self.get_assembly_name()
#		return non_preferred_haplotype_assembly_name

	def haplotype_clause(self):
		haplotype_clause = ''
		if self.yaml_key_has_content('haplotype_to_curate'):
			haplotype_clause = self.yaml['haplotype_to_curate'] + '.'
		return haplotype_clause

	def has_two_haplotypes(self):
		if len( self.get_haplotypes() ) > 1:
			return True
		else:
			return False

	def get_haplotypes(self):
		if 'haplotype_to_curate' in self.yaml:
			return [self.yaml['haplotype_to_curate']]

		haplotype_specific_assembly_names = [
			'hap1',
			'hap2',
			'maternal',
			'paternal',
		]

		haplotypes = []
		for haplotype_specific_assembly_name in haplotype_specific_assembly_names:
			if self.yaml_key_has_content(haplotype_specific_assembly_name):	
				haplotypes.append(haplotype_specific_assembly_name)
		return haplotypes	

	def get_common_name(self):
		species_and_common_name = self.get_custom_field('species_name')
		species_match = re.match(r'(\S+\s+\S+(?:\s+\S+)?)\s+\((.*)\)', species_and_common_name)
		if species_match:
			common_name = species_match.group(2)
			if not re.search(r'\S', common_name):
				common_name = None
			return(common_name)
		else:
			exit('Non-standard species name in ticket: ' + species_and_common_name)

	def get_geval_database_fields(self):
		geval_database = self.get_custom_field('gEVAL_database')
		if geval_database == None:
			return []
		geval_database_fields = re.split('_', geval_database)
		if len(geval_database_fields) < 2:
			exit('Non-standard gEVAL DB name: ' + geval_database)
		return geval_database_fields

	def sample_and_suffix_from_geval_database(self):
		if self.get_project() in ['RC','DS'] and self.get_custom_field('gEVAL_database') == None:
			return self.get_custom_field('sample_id') + '_1'
		else:
			geval_database_fields = self.get_geval_database_fields()
			if len(geval_database_fields) == 4:
				return '_'.join(geval_database_fields[2:])
			elif len(geval_database_fields) == 2:
				return '_'.join(geval_database_fields)
			elif re.match('(idAnoArabHR|odEunFrag1)', self.get_custom_field('gEVAL_database')):
				return self.get_custom_field('gEVAL_database')
			else:
				exit('Non-standard gEVAL DB name: ' + self.get_custom_field('gEVAL_database'))

	def sample_from_geval_database(self):
		if self.get_project() in ['RC', 'DS']:
			return self.get_custom_field('sample_id')
		else:
			geval_database_fields = self.get_geval_database_fields()
			if len(geval_database_fields) == 4:
				return '_'.join(geval_database_fields[2:-1])
			elif len(geval_database_fields) == 2:
				return '_'.join(geval_database_fields)	

	def correct_old_assembly_paths(self, assembly_path):
		assembly_path = re.sub('scratch116(?=/tol/projects/(darwin|genomeark|vgp))', 'scratch124', assembly_path)
		assembly_path = re.sub('scratch116(?=/tol/(projects/badass|teams/durbin))', 'scratch123', assembly_path)
		return assembly_path

	def get_local_assembly_for_label(self, label):
		if label in self.yaml:
			assembly = self.yaml[label]
			if assembly == None or re.match(r'^\s*$', assembly):
				return None
			assembly = self.correct_old_assembly_paths(assembly)
			if ('data_location' in self.yaml and (self.yaml['data_location'] in ['S3','FTP','ERGA','Sanger RO'])) or re.match(r'^s3\:', assembly) or re.match('^http', assembly) or re.match('^ftp', assembly):
				assembly = self.get_assembly_draft_version_dir() + os.path.split(assembly)[1]
			elif ('data_location' in self.yaml and (self.yaml['data_location'] in ['INSDC','NCBI','ENA'])):
				if not re.search('/', assembly): # Treat as accession if it's not a path
					assembly = self.get_assembly_draft_version_dir() + assembly + '.fa.gz'
	
			return assembly
		else:
			return None

#	def get_local_pacbio_read_dir(self):
#		pacbio_read_dir = self.yaml['pacbio_read_dir']
#		if ('data_location' in self.yaml and (self.yaml['data_location'] in ['S3','FTP','ERGA','Sanger RO'])) or re.match('^s3\:', assembly) or re.match('^http', assembly) or re.match('^ftp', assembly):
#			pacbio_read_dir = self.get_assembly_draft_version_dir() + '../../../genomic_data/' + self.get_custom_field('sample_id') + '/pacbio/'
#			exit('No local dir available')
#		elif ('data_location' in self.yaml and (self.yaml['data_location'] in ['INSDC','NCBI','ENA'])):
#		return pacbio_read_dir

	def get_assembly_labels(self):
		possible_assembly_yaml_labels = [
			'primary',
			'haplotigs',
			'mito',
			'plastid',
			'mt',
			'paternal',
			'maternal',
			'hap1',
			'hap2',
		]

		assembly_labels = []
		for possible_assembly_yaml_label in possible_assembly_yaml_labels:
			if possible_assembly_yaml_label in self.yaml and self.yaml[possible_assembly_yaml_label] != None and re.search(r'\S', self.yaml[possible_assembly_yaml_label]):
				assembly_labels.append(possible_assembly_yaml_label)
		return assembly_labels

	def get_assemblies_by_label(self):
		assemblies_by_label = {}
		for assembly_label in self.get_assembly_labels():
			assemblies_by_label[assembly_label] = self.get_local_assembly_for_label(assembly_label)

		return assemblies_by_label

	def validate_yaml(self):
		yaml_is_valid = True
		# Do all assembly files exist?
		local_assembly_for_label = self.get_assemblies_by_label()
		for label in local_assembly_for_label:
			if not os.path.isfile(local_assembly_for_label[label]):
				self.add_comment(f'The YAML specifies file {local_assembly_for_label[label]} as assembly {label} but it does not exist.')
				yaml_is_valid = False

		# Can we write to the draft directory?
		if not os.access(self.get_assembly_draft_version_dir(), os.R_OK):
			self.add_comment(f'Cannot read from draft directory.')
			yaml_is_valid = False
		if not os.access(self.get_assembly_draft_version_dir(), os.W_OK):
			self.add_comment(f'Cannot write to draft directory.')
			yaml_is_valid = False

		return yaml_is_valid

	def get_assemblies(self):
		return list( self.get_assemblies_by_label().values() )

	def get_main_assembly_label(self):
		# Goes through primary, paternal, and maternal, and returns the first of those that it finds
		if 'haplotype_to_curate' in self.yaml:
			return self.yaml['haplotype_to_curate']

		possible_main_assembly_yaml_labels = [
			'primary',
			'paternal',
			'maternal',
			'hap1',
			'hap2',
			'mito', # Note that mito is just intended as a fallback for special cases with MT only
		]
		for possible_main_assembly_yaml_label in possible_main_assembly_yaml_labels:
			if self.yaml_key_has_content(possible_main_assembly_yaml_label):
				return possible_main_assembly_yaml_label
		return None

	def get_yaml_main_assembly(self):
		# Goes through primary, paternal, and maternal, and returns the first of those that it finds
		return self.yaml[self.get_main_assembly_label()]

	def get_main_assembly(self):
		# Goes through primary, paternal, and maternal, and returns the first of those that it finds
		return self.get_local_assembly_for_label(self.get_main_assembly_label())

	def get_curated_file_name_for_type(self):
		curated_file_name_for_type = {}
		if len(self.get_haplotypes()) == 0:
			curated_file_name_for_type = {
				'fasta': {
					'additional_haplotigs': self.get_assembly_name() + ".additional_haplotigs.curated.fa",
					'primary': self.get_assembly_name() + ".primary.curated.fa",
				},
				'chromosome_list_csv': {
				}
			}

			if self.yaml_key_is_true('combine_for_curation'):
				curated_file_name_for_type['fasta']['additional_haplotigs'] = self.get_assembly_name() + ".all_haplotigs.curated.fa"

			assembly_extensions = ['primary', 'all_haplotigs']

			for assembly_extension in assembly_extensions:
				curated_file_name_for_type['chromosome_list_csv'][assembly_extension] = f'{self.get_assembly_name()}.{assembly_extension}.chromosome.list.csv'
		else:
			curated_file_name_for_type = {
				'fasta': {},
				'chromosome_list_csv': {},
			}

			for haplotype in self.get_haplotypes():
				assembly_name = self.get_assembly_name_for_haplotype(haplotype)
				curated_file_name_for_type['fasta'][haplotype] = assembly_name + '.primary.curated.fa'
				if self.yaml_key_is_true('combine_for_curation'):
					curated_file_name_for_type['fasta'][f'{haplotype}_all_haplotigs'] = assembly_name + ".all_haplotigs.curated.fa"
				else:
					curated_file_name_for_type['fasta'][f'{haplotype}_additional_haplotigs'] = assembly_name + '.additional_haplotigs.curated.fa'
				curated_file_name_for_type['chromosome_list_csv'][haplotype] = f'{assembly_name}.primary.chromosome.list.csv'

		return curated_file_name_for_type

	def get_organelle_labels(self):
		organelle_labels = [
			'mito',
			'plastid',
			'mt',
		]
		return organelle_labels

	def get_final_assembly_labels(self):
		organelle_labels = self.get_organelle_labels()
		final_assembly_labels = []

		haplotypes = self.get_haplotypes()
		if len(haplotypes) > 0:
			for haplotype in haplotypes:
				final_assembly_labels.append(haplotype)
				final_assembly_labels.append(f'{haplotype}.all_haplotigs')
		else:
			for assembly_label in self.get_assembly_labels():
				if assembly_label not in organelle_labels:
					if assembly_label == 'haplotigs' and not self.is_haploid():
						final_assembly_labels.append('all_haplotigs')
					else:
						final_assembly_labels.append(assembly_label)

		return final_assembly_labels

	def get_final_stems(self):

		organelle_labels = self.get_organelle_labels()
		final_stems = []

		haplotypes = self.get_haplotypes()
		if len(haplotypes) > 0:
			for haplotype in haplotypes:
				haplotype_base_stem = self.get_custom_field('sample_id') + f'.{haplotype}.' + self.get_release_version()
				final_stems.append(f'{haplotype_base_stem}.primary')
				final_stems.append(f'{haplotype_base_stem}.all_haplotigs')
		else:		
			final_stems.append(self.get_custom_field('sample_id') + '.' + self.get_release_version() + '.primary')
			if not self.is_haploid():
				final_stems.append(self.get_custom_field('sample_id') + '.' + self.get_release_version() + '.all_haplotigs')

		return final_stems

	def get_haplotig_chromosome_mode(self):
		curated_file_name_for_type = self.get_curated_file_name_for_type()
		haplotig_chromosome_list_csv = '/NO_SUCH_FILE'

		if len(self.get_haplotypes()) > 1:
			if 'hap2' in curated_file_name_for_type['chromosome_list_csv']:
				haplotig_chromosome_list_csv = self.get_curated_tolid_dir() + '/' + curated_file_name_for_type['chromosome_list_csv']['hap2']
			elif 'paternal' in curated_file_name_for_type['chromosome_list_csv']:
				haplotig_chromosome_list_csv = self.get_curated_tolid_dir() + '/' + curated_file_name_for_type['chromosome_list_csv']['paternal']
		else:
			if 'all_haplotigs' in curated_file_name_for_type['chromosome_list_csv']:
				haplotig_chromosome_list_csv = self.get_curated_tolid_dir() + '/' + curated_file_name_for_type['chromosome_list_csv']['all_haplotigs']

		haplotig_chromosomes = False
		if os.path.isfile(haplotig_chromosome_list_csv):
			haplotig_chromosomes = True
		#elif self.yaml_key_is_true('haplotig_chromosomes') or os.path.isfile(haplotig_chromosome_list_csv):
		#	exit(f'Inconsistent haplotig chromosome information: YAML says {self.yaml_key_is_true("haplotig_chromosomes")} but files say {os.path.isfile(haplotig_chromosome_list_csv)}. Expecting file at {haplotig_chromosome_list_csv}.')
		return haplotig_chromosomes

	def is_there_a_chromosome_csv_for_haplotype(self, haplotype):
		haplotig_chromosome_list_csv = self.get_curated_tolid_dir() + '/' + self.get_curated_file_name_for_type()['chromosome_list_csv'][haplotype]
		return os.path.isfile(haplotig_chromosome_list_csv)

	def full_name_for_username(self, username):
		if username == None:
			return None
		finger_output = subprocess.check_output(['finger', '-s', username]).decode('ASCII')
		finger_output_lines = re.split(r'\n', finger_output)
		finger_output_fields = re.split(r'\s{2,}', finger_output_lines[1])
		return(finger_output_fields[1])

	def get_directory_taxon(self):
		return self.get_directory_taxon_for_sample_id(self.get_custom_field('sample_id'))

	def get_directory_taxon_for_sample_id(self, sample_id):
		if self.get_project() == 'CR':
			sample_prefix = self.yaml['specimen'][0]
		else:
			sample_prefix = sample_id[0]
		if sample_prefix in self.taxon_for_sample_prefix:
			return self.taxon_for_sample_prefix[sample_prefix]
		else:
			exit('Cannot find a taxon for prefix ' + sample_prefix)

	# Get the curation directory for a given sample-name in GitLab
	def get_gitlab_dir(self):
		# Derive from the species name
		directory_taxon = self.get_tol_group_from_species()

		#directory_taxon = None
		#if self.get_contamination_directory() != None:
		#	taxon_regex = '/([^/]+)/' + re.sub('\s', '_', self.get_species())
		#	taxon_from_contamination_match = re.search(taxon_regex, self.get_contamination_directory())
		#	if taxon_from_contamination_match:
		#		directory_taxon = taxon_from_contamination_match.group(1)
		# Fallback is to derive the directory taxon from the sample ID
		if directory_taxon == None:
			directory_taxon = self.get_directory_taxon()

		return directory_taxon + '/' + self.sample_from_geval_database() + '/'

	def release_directory_to_assembly_version(self, release_directory):
		release_directory_fields = re.split(r'\.', release_directory)
		assembly_version_fields = []
		for release_directory_field in release_directory_fields:
			release_directory_field = re.sub('asm', 'a', release_directory_field)
			release_directory_field = re.sub('purge', 'pu', release_directory_field)
			release_directory_field = re.sub('polish', 'p', release_directory_field)
			release_directory_field = re.sub('scaff', 's', release_directory_field)
			assembly_version_fields.append(release_directory_field)
		assembly_version = '.'.join(assembly_version_fields)
		self.set_custom_field('version', assembly_version)
		return assembly_version

	def assembly_version_to_release_directory(self):
		if self.get_project() == 'CR':
			release_directory = self.yaml['specimen'] + '.PB.asm1'

		else:
			assembly_version_fields = re.split(r'\.', self.get_custom_field('version'))
			release_directory_fields = []
			for assembly_version_field in assembly_version_fields:
				v_to_d = {
					'a': 'asm',
					'pu': 'purge',
					'p': 'polish',
					's': 'scaff',
				}

				assembly_version_parts_match = re.match(r'(\D+)(\d+)', assembly_version_field)
				if assembly_version_parts_match:
					assembly_version_name = assembly_version_parts_match.group(1)
					assembly_version_number = assembly_version_parts_match.group(2)
					if assembly_version_name in v_to_d:
						assembly_version_field = v_to_d[assembly_version_name] + assembly_version_number
				
				release_directory_fields.append(assembly_version_field)
			release_directory = '.'.join(release_directory_fields)
		return release_directory

	# POSSIBILITIES
	# Data dir and release dir present different issues
	# get directory from YAML if it exists
	# Get directory from .contamination file if it exists
	# Put release dir in GRIT tier if not
	# (Perhaps make that the default)
	# If constructing directory ab initio, check if it already exists if it's Darwin

	# Get the draft dir, ie the dir where contamination checking is carried out
	def get_assembly_draft_version_dir(self):

		# Get from contamination directory if possible
		assembly_draft_dir = self.get_contamination_directory()

		# Failing that, get it from YAML
		# This should *only* be done for Sanger RW cases
		if assembly_draft_dir == None:
			if 'data_location' not in self.yaml or self.yaml['data_location'] == 'Sanger RW':
				assembly_draft_dir = self.get_assembly_draft_version_dir_from_yaml()

		# Failing that, get ab initio
		if assembly_draft_dir == None:
			assembly_draft_dir = self.get_assembly_draft_version_dir_ab_initio()

		# If all the above fails, warn and return none
		if assembly_draft_dir == None:
			print('Could not determine assembly draft dir')
		return assembly_draft_dir

	def get_species_data_dir(self):

		species_data_dir = None

		# Derive from assembly draft dir if possible
		assembly_draft_dir = self.get_assembly_draft_version_dir()

		# The directory used for the draft dir will be used as a basis if it lies within one of the approved directories
		approved_directories = [
			self.tol_dir,
			self.old_tol_dir,
			self.grit_dir,
			self.scratch122_dir,
			'/lustre/scratch123/tol/teams/durbin/data/',
			'/lustre/scratch123/tol/teams/grit/',
			'/lustre/scratch123/tol/teams/lawniczak/data/',
			'/lustre/scratch116/tol/teams/durbin/data/',
			'/lustre/scratch116/tol/teams/lawniczak/data/',
			'/lustre/scratch123/tol/teams/meier/data/',
			'/lustre/scratch125/tol/teams/meier/data/',
			'/lustre/scratch122/tol/projects/meier-tmp/',
			'/lustre/scratch123/tol/teams/blaxter/projects/tol-nemotodes/data/',
			'/lustre/scratch126/tol/teams/jaron/data/',
			'/lustre/scratch126/tol/teams/lawniczak/',
			'/lustre/scratch123/tol/projects/',
		]

		# species_data_dir_regex = '^((' + "|".join(approved_directories) + ').*' + re.sub('\s', '_', self.get_species())  + '/)'
		# Note: Allowing for this sample ID is a temporary fix to allow Chris Laumer's assemblies- revert to the above afterwards
		species_regex = re.sub(r'[\s\']+', '_', self.get_species())
		species_regex = re.sub(r'_sp\._', '_.*', species_regex)
		species_regex = re.sub(r'_$', '', species_regex)

#		species_data_dir_regex = '^((' + "|".join(approved_directories) + ').*' + species_regex  + f'(/{self.get_custom_field("sample_id")})?' + '/)'

		species_data_dir_regex = '^(.*/)assembly/draft/'
		species_data_dir_match = re.match(species_data_dir_regex, assembly_draft_dir)
		if species_data_dir_match:
			species_data_dir = species_data_dir_match.group(1)
		if species_data_dir == None:
			species_data_dir = self.get_species_data_dir_ab_initio()

#		if assembly_draft_dir != None:
#			# For ASG or ERGA, use the draft dir as a source regardless of species name
#			if self.get_issue_type() in ('ASG', 'ERGA'):
#				asg_regex = f'({self.tol_dir}(asg|darwin|erga)/data/[^/]+/[^/]+/)'
#				species_data_dir_match = re.match(asg_regex, assembly_draft_dir)
#				if species_data_dir_match:
#					species_data_dir = species_data_dir_match.group(1)
#			# Do similarly for Darwin and ERGA MAGs
#			elif self.get_issue_type() in ('Darwin','ERGA') and (self.assembly_is_mag() or self.assembly_is_from_markerscan()):
#				darwin_regex = f'({self.tol_dir}(darwin|erga)/data/[^/]+/[^/]+/)'
#				species_data_dir_match = re.match(darwin_regex, assembly_draft_dir)
#				if species_data_dir_match:
#					species_data_dir = species_data_dir_match.group(1)
#			else:
#				species_data_dir_match = re.match(species_data_dir_regex, assembly_draft_dir)
#				if species_data_dir_match:
#					species_data_dir = species_data_dir_match.group(1)
#		if species_data_dir == None:
#			species_data_dir = self.get_species_data_dir_ab_initio()

		return species_data_dir

	def get_assembly_draft_version_dir_from_yaml(self):
		# Return None if not available
		if not self.is_yaml_available() or 'projects' not in self.yaml or len(self.yaml['projects']) == 0:
			return None
		# Only do this for Sanger RW projects (the default)- in other cases, the YAML may have an original download location
		if ('data_location' in self.yaml and self.yaml['data_location'] != 'Sanger RW') or re.match(r'^(s3\:|ftp|http)', self.get_yaml_main_assembly()):
			return None
		assembly = self.get_main_assembly()
		assembly = self.correct_old_assembly_paths(assembly)
		(assembly_dir, assembly_file) = os.path.split(assembly)
		return assembly_dir + '/'

	def get_species_data_dir_ab_initio(self):
		# Assumes this is a Darwin project unless it's a GenomeArk case
		species_data_dir = None
		directory_from_species = re.sub(r'[\s(),-]+', '_', self.get_species())
		directory_from_species = re.sub(r'_+$', '', directory_from_species)
		if ('data_location' in self.yaml and self.yaml['data_location'] in ('S3')) or self.get_release_version() == '0':
			# species_data_dir = self.grit_dir + 'vgp/'  + 'data/' + self.get_directory_taxon() + '/' + re.sub('\s', '_', self.get_species()) + '/'
			species_data_dir = self.tol_dir + 'genomeark/'  + 'data/' + self.get_directory_taxon() + '/' + directory_from_species + '/'
		elif self.get_project_list_from_yaml()[0] == 'ERGA':
			species_data_dir = self.tol_dir + 'external_curation/'  + 'data/' + self.get_directory_taxon() + '/' + directory_from_species + '/'
		elif self.get_project_list_from_yaml()[0] == 'CCGP' or ('data_location' in self.yaml and self.yaml['data_location'] in ('FTP', 'Sanger RO')):
			species_data_dir = self.tol_dir + 'external_curation/'  + 'data/' + self.get_directory_taxon() + '/' +directory_from_species + '/'
		elif self.get_project_list_from_yaml()[0] == 'ASG':
			species_data_dir = self.tol_dir + 'asg/'  + 'data/' + self.get_directory_taxon() + '/' + directory_from_species + '/'
		elif self.get_project_list_from_yaml()[0] == 'VGP':
			species_data_dir = self.tol_dir + 'vgp/'  + 'data/' + self.get_directory_taxon() + '/' + directory_from_species + '/'
		else:
			species_data_dir = self.tol_dir + 'darwin/' + 'data/' + self.get_directory_taxon() + '/' + directory_from_species + '/'
			if not os.path.isdir(species_data_dir): # I don't have the ability to create these directories
				exit('Release dir ' + species_data_dir + ' does not exist')

		return species_data_dir

	def get_assembly_draft_version_dir_ab_initio(self):
		return self.get_species_data_dir_ab_initio() + 'assembly/draft/' + self.assembly_version_to_release_directory() + '/'

	def get_curated_tolid_dir(self):
		return self.get_species_data_dir() + 'assembly/curated/' + self.get_assembly_name_without_haplotype() + '/'

	def get_curated_tolid_dir_ab_initio(self):
		return self.get_species_data_dir_ab_initio() + 'assembly/curated/' + self.get_assembly_name_without_haplotype() + '/'

#	def get_insdc_dir(self):
#		return self.get_curated_tolid_dir()

	def get_assembly_submission_dir(self):
		sample_and_version = self.get_custom_field('sample_id') + '.' + self.get_release_version()
		submissions_base_dir = '/nfs/compgen-03/vgp_submissions/'
		assembly_submission_dir = submissions_base_dir + sample_and_version + '/'
		return assembly_submission_dir

	def get_assembly_accessions(self):
		if self.get_custom_field('accession_data') == None:
			return()
		accession_fields = re.split(r'\s*\|\s*', self.get_custom_field('accession_data'))
		assembly_accessions = []
		for accession_field in accession_fields:
			assembly_match = re.match('GCA_', accession_field)
			if assembly_match:
				assembly_accessions.append(accession_field)
		return assembly_accessions

	def get_contamination_directory(self):
		contamination_file = self.get_custom_field('contamination_files')
		if contamination_file == None:
			return None
		contamination_directory = os.path.dirname(contamination_file) + '/'
		contamination_directory = self.correct_old_assembly_paths(contamination_directory)
		if not os.path.isdir(contamination_directory):
			exit('Cannot find contamination directory ' + contamination_directory + '. Contamination file field in JIRA may be outdated or erroneous.')
		return contamination_directory

	def get_genomic_data_dir(self):
		return(self.get_species_data_dir() + 'genomic_data/' + self.get_custom_field('sample_id') + '/')

	def get_genomic_data_dir_from_yaml(self):
		if self.yaml_key_has_content('pacbio_read_dir'):
			genomic_data_dir_match = re.match('^(.*genomic_data)', self.yaml['pacbio_read_dir'])
			if genomic_data_dir_match:
				genomic_data_dir = genomic_data_dir_match.group(1) + '/'
				return genomic_data_dir
			else:
				exit(f'Cannot identify genomic data dir in {self.yaml["pacbio_read_dir"]}')
		else:
			exit('No pacbio data dir available to derive genomic data dir from')

	def get_pacbio_fasta_dir(self, create_if_not_found = False):
		pacbio_fasta_dir = self.get_genomic_data_dir() + 'pacbio/fasta/'
		if not os.path.isdir(pacbio_fasta_dir):

			ont_fasta_dir =  self.get_genomic_data_dir() + 'ont/fasta/'

			if os.path.isdir(ont_fasta_dir):
				return ont_fasta_dir
			elif 'pacbio_read_dir' in self.yaml and not(self.yaml_key_has_content('data_location') and self.yaml['data_location'] in ('S3','FTP','ERGA')):
				pacbio_fasta_dir = self.yaml['pacbio_read_dir'] + '/fasta/'
				if not os.path.isdir(pacbio_fasta_dir):
					if create_if_not_found:
						os.makedirs(pacbio_fasta_dir)
					else:
						exit(f'Cannot find Pacbio read dir: {pacbio_fasta_dir} does not exist')
			else:
				if create_if_not_found:
					os.makedirs(pacbio_fasta_dir)
				else:
					exit(f'Cannot find Pacbio read dir: {pacbio_fasta_dir} does not exist')
		return pacbio_fasta_dir
		
	def get_stats_dict(self):
		stats_dict = {}
		stats = self.get_custom_field('assembly_statistics')
		# We only want the 'after' stats
		stats_lines = re.split(r'\n', stats)
		section_name = 'SCAFFOLD'
		for stats_line in stats_lines:
			if re.search('contigs', stats_line):
				section_name = 'CONTIG'
			values_search_result = re.search(r'^(\S+)\s+(\d+)\s+(\d+)', stats_line)
			if values_search_result:
				if section_name not in stats_dict:
					stats_dict[section_name] = {}
				stats_dict[section_name][values_search_result.group(1).upper()] = int(values_search_result.group(3))
		return stats_dict

	def get_project(self):
		return self.issue_json['fields']['project']['key']

	def set_field(self, field_name, value):
		jira_method = 'issue/'
		query_data = self.key
		jira_query = jira_method + query_data

		data_to_put = {
			"fields" : {
				field_name: value,
			},
		}
		self.jira_put(jira_query, data_to_put)

	def add_comment(self, comment_text):
		query_data = self.key
		jira_query = 'issue/' + query_data + '/comment'

		data_to_put = {
			"body" : comment_text,
		}

		self.jira_put(jira_query, data_to_put, post=True)

	def add_label(self, label):
		query_data = self.key
		jira_query = 'issue/' + query_data

		data_to_put = {
			'update': {
				'labels': [{'add': label}],
			}
		}
		self.jira_put(jira_query, data_to_put)

	def remove_label(self, label):
		query_data = self.key
		jira_query = 'issue/' + query_data

		data_to_put = {
			'update': {
				'labels': [{'remove': label}],
			}
		}
		self.jira_put(jira_query, data_to_put)

	def get_labels(self):
		query_data = self.key
		return self.issue_json['fields']['labels']

	def get_update_time(self):
		update_time_text =self.issue_json['fields']['updated']
		return self.jira_time_to_datetime(update_time_text)

	def jira_time_to_datetime(self, jira_time):
		jira_time = re.sub('\..*','', jira_time)
		jira_time_as_datetime = datetime.strptime(jira_time, '%Y-%m-%dT%H:%M:%S')

		return jira_time_as_datetime

	def assembly_is_mag(self):
		if 'assembly_type' in self.yaml and self.yaml['assembly_type'] in ['primary metagenome', 'binned metagenome', 'Metagenome-Assembled Genome (MAG)']:
			return True
		else:
			return False

	def assembly_is_primary_metagenome(self):
		if 'assembly_type' in self.yaml and self.yaml['assembly_type'] in ['primary metagenome']:
			return True
		else:
			return False

	def assembly_is_binned_metagenome(self):
		if 'assembly_type' in self.yaml and self.yaml['assembly_type'] in ['binned metagenome']:
			return True
		else:
			return False

	def assembly_is_asg_draft_submission(self):
		if self.get_project_list_from_yaml()[0]== 'ASG' and self.yaml_key_has_content('cobiont_status') and self.yaml['cobiont_status'] == 'cobiont' and self.yaml['jira_queue'] == 'DS':
			return True
		else:
			return False

	def assembly_is_darwin_cobiont_draft_submission(self):
		if self.get_project_list_from_yaml()[0]== 'Darwin' and self.yaml_key_has_content('cobiont_status') and self.yaml['cobiont_status'] == 'cobiont' and self.yaml['jira_queue'] == 'DS':
			return True
		else:
			return False

	def assembly_is_faculty__draft_submission(self):
		if self.get_project_list_from_yaml()[0]== 'Faculty' and self.yaml_key_has_content('cobiont_status') and self.yaml['cobiont_status'] == 'cobiont' and self.yaml['jira_queue'] == 'DS':
			return True
		else:
			return False

	def assembly_is_prokaryotic_cobiont(self):
		if 'cobiont_status' in self.yaml and self.yaml['cobiont_status'] == 'cobiont' and 'domain' in self.yaml and self.yaml['domain'] in ('bacteria', 'archaea'):
			return True
		else:
			return False

	def assembly_is_from_markerscan(self):
		#if self.get_project_list_from_yaml()[0]== 'Darwin' and self.yaml_key_has_content('cobiont_status') and self.yaml['cobiont_status'] == 'cobiont' and self.yaml['jira_queue'] == 'DS' and 'markerscan' in self.get_pipeline_software():
		if self.yaml_key_has_content('assembly_source') and self.yaml['assembly_source'].lower() == 'markerscan':
			return True
		else:
			return False

	def assign(self, assignee):
		query_data = self.key
		jira_query = 'issue/' + query_data

		data_to_put = {
			'fields' : {
				'assignee': {'name': assignee},
			},
		}
		self.jira_put(jira_query, data_to_put)

	def rename_scaffolds_for_assembly(self, original_file_name, scaffname='SCAFFOLD'):
		# Copy to temp
		temp_file_name =  original_file_name + '.original_scaffold_names.fa.gz'
		os.system(f'mv {original_file_name} {temp_file_name}')
		# Get script dir
		script_dir = os.path.dirname(__file__)
		mapping_name = original_file_name + '.renaming_map'
		original_file_name_unzipped = re.sub(r'\.gz','',original_file_name)
		renaming_command = f'python3 {script_dir}/../../contamination_screen/scripts/rename_scaffolds.py --input {temp_file_name} --output {original_file_name_unzipped} --map {mapping_name} --scaffname {scaffname}'
		renaming_result = os.system(renaming_command)
		if renaming_result != 0:
			self.add_comment('Error in renaming')
			self.add_label('contamination_screen_failure')
			exit('Error in renaming')
		os.system(f'gzip -n {original_file_name_unzipped}')
		os.remove(temp_file_name)

	def rename_assemblies(self):
		assemblies_by_label = self.get_assemblies_by_label()
		for label in assemblies_by_label:
			if self.yaml_key_has_content('combine_for_curation') and (self.yaml['combine_for_curation'] == True or re.match('true', self.yaml['combine_for_curation'].lower())):
				if label in ('primary', 'hap1', 'maternal'):
					self.rename_scaffolds_for_assembly(assemblies_by_label[label], 'HAP1_SCAFFOLD')
				elif label in ('haplotigs','hap2', 'paternal'):
					self.rename_scaffolds_for_assembly(assemblies_by_label[label], 'HAP2_SCAFFOLD')
				else:
					self.rename_scaffolds_for_assembly(assemblies_by_label[label])	
			elif label != 'haplotigs' and not self.assembly_is_mag() and not self.assembly_is_asg_draft_submission():
				self.rename_scaffolds_for_assembly(assemblies_by_label[label])

	def filter_scaffolds_by_size_for_assembly(self, original_file_name, max_size):
		# Copy to temp
		filtered_file_name =  original_file_name + '.filtered.fa'
		# Get script dir
		script_dir = os.path.dirname(__file__)
		filter_command = f'python3 {script_dir}/../scripts/filter_scaffolds_by_size.py --fasta_in {original_file_name} --fasta_out {filtered_file_name} --max_size {max_size}'
		print(filter_command)
		filter_result = os.system(filter_command)
		if filter_result != 0:
			self.add_comment('Error in filtering')
			self.add_label('contamination_screen_failure')
			exit('Error in filtering')
		os.system(f'gzip -n {filtered_file_name}')

	def filter_scaffolds_by_size_for_all_assemblies(self, max_size):
		assemblies_by_label = self.get_assemblies_by_label()
		for label in assemblies_by_label:
			if not self.assembly_is_mag() and not self.assembly_is_asg_draft_submission():
				self.filter_scaffolds_by_size_for_assembly(assemblies_by_label[label], max_size)

	def break_large_chromosomes_for_assembly(self, original_file_name):
		# Copy to temp
		temp_file_name =  original_file_name + '.original_chromosomes.fa.gz'
		os.system(f'mv {original_file_name} {temp_file_name}')
		# Get script dir
		script_dir = os.path.dirname(__file__)
		original_file_name_unzipped = re.sub(r'\.gz','',original_file_name)
		breaking_command = f'python3 {script_dir}/../scripts/break_large_chromosomes.py --force --fasta_in {temp_file_name} --fasta_out {original_file_name_unzipped}'
		breaking_result = os.system(breaking_command)
		if breaking_result != 0:
			self.add_comment('Error in chromosome breaking')
			self.add_label('contamination_screen_failure')
			exit('Error in chromosome breaking')
		os.system(f'gzip -n {original_file_name_unzipped}')
		os.remove(temp_file_name)

	def break_large_chromosomes_for_all_assemblies(self):
		assemblies_by_label = self.get_assemblies_by_label()
		for label in assemblies_by_label:
			if not self.assembly_is_mag() and not self.assembly_is_asg_draft_submission():
				self.break_large_chromosomes_for_assembly(assemblies_by_label[label])

	def is_haploid(self):
		if self.is_yaml_available():
			if 'ploidy' in self.yaml and self.yaml['ploidy'] == 'haploid':
				return True
			elif 'haploid' in self.get_labels():
				return True
			else:
				return False
			
	def get_sequence_lengths(self, fasta_file):
		sequence_lengths = []
		fasta_input_handle = None

		if re.search('gz$', fasta_file):
				fasta_input_handle = gzip.open(fasta_file, "rt")
		else:
				fasta_input_handle = open(fasta_file, "rt")

		for record in SeqIO.parse(fasta_input_handle, "fasta"):
			sequence_lengths.append( len(record.seq) )
		fasta_input_handle.close()

		return sequence_lengths
	
	def get_file_size(self, file):
		stat_result = os.stat(file)
		return stat_result.st_size
	
	def get_largest_assembly_size(self):
		largest_assembly_size = 0
		for assembly in self.get_assemblies():
			assembly_size = self.get_file_size(assembly)
			if assembly_size > largest_assembly_size:
				largest_assembly_size = assembly_size

		return largest_assembly_size
	
	def get_farm_version(self):
		lsid_result = subprocess.run(['lsid'], capture_output=True)
		lsid_search_result = re.search(r'My cluster name is (\S+)', lsid_result.stdout.decode('ascii'))
		if lsid_search_result:
			return lsid_search_result.group(1)
		else:
			exit('Cannot determine farm identity using LSID')

	def get_internal_projects(self):
		return self.internal_projects

	def get_high_priority_projects(self):
		return self.high_priority_projects 
	
	def get_metagenome_projects(self):
		return self.metagenome_projects 
	
	def get_slack_notification_projects(self):
		return self.slack_notification_projects
	
	def get_s3_main_assembly_dir(self):
		sections = os.path.split(self.yaml[self.get_main_assembly_label()])
		return sections[0] + '/'

	def s3_ls_main_assembly_dir(self):
		print(f'Listing {self.get_s3_main_assembly_dir()}')
		self.s3_ls(self.get_s3_main_assembly_dir())

	def s3_check_assemblies(self):
		for assembly_label in (self.get_assembly_labels()):
			print(f'{assembly_label} should be at {self.yaml[assembly_label]}')
			self.s3_ls(self.yaml[assembly_label])

	def s3_validate_assemblies(self):
		assemblies_valid = True
		error_message = ''
		for assembly_label in (self.get_assembly_labels()):
			if self.s3_check_location(self.yaml[assembly_label]) == None:
				assemblies_valid = False
				error_message += f'{assembly_label} not found at {self.yaml[assembly_label]}. Cannot download assembly.\n'

		if error_message != '':
			self.add_comment(error_message)

		return assemblies_valid

	def s3_ls(self, s3_location):
		s3_result = self.s3_check_location(s3_location)
		if s3_result == None:
			print('\tFile not found')
		else:
			print('\t' + s3_result)

	def s3_check_location(self, s3_location):
		s3_result = subprocess.run(['aws', 's3', '--profile', 'grit', 'ls', s3_location], capture_output=True)
		if s3_result.stdout.decode('ascii') == '':
			return None
		else:
			return(s3_result.stdout.decode('ascii'))

#		if lsid_search_result:
#			return lsid_search_result.group(1)

#		os.system(f'aws s3 --profile grit ls {s3_location}')