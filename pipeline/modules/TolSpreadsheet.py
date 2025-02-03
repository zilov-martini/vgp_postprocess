import os
import tempfile
import csv
import re
import urllib.parse

class TolSpreadsheet:
	spreadsheet_url = 'https://docs.google.com/spreadsheets/d/1RKubj10g13INd4W7alHkwcSVX_0CRvNq0-SRe21m-GM'
	csv_download_suffix = '/gviz/tq?tqx=out:csv&sheet='
	open_handles = []

	def __init__(self, sheet_name='Status', spreadsheet_url = None):
		self.sheet_name = sheet_name
		if spreadsheet_url != None:
			self.spreadsheet_url = spreadsheet_url

		(handle, self.spreadsheet_file) = tempfile.mkstemp()
		os.close(handle)
		os.system(f'curl -s "{self.spreadsheet_url}{self.csv_download_suffix}{urllib.parse.quote(self.sheet_name)}" > {self.spreadsheet_file}')

	def csv_reader(self):
		spreadsheet_handle = open(self.spreadsheet_file, newline='')
		self.open_handles.append(spreadsheet_handle)
		spreadsheet_reader = csv.DictReader(spreadsheet_handle, delimiter=',', quotechar='"')
		return spreadsheet_reader

	def run_refs_for_sample(self,sample):
		sample_column = 'sample'

		for row in self.csv_reader():
			spreadsheet_sample = row[sample_column]
			spreadsheet_sample = re.sub('\..*$', '', spreadsheet_sample) # Eliminate mat/pat distinctions
			if spreadsheet_sample == sample:
				run_refs = re.split(',', row['runs'])
				if row['runs'] == '':
					run_refs = []
				return(run_refs)
		exit('No runs found')

	def __del__(self):
		for open_handle in self.open_handles:
			open_handle.close()
		os.system(f'rm {self.spreadsheet_file}')
