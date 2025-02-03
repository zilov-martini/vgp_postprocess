import requests
import netrc
import json
import subprocess
import re

class GritJiraProject:
	host_name = "grit-jira.sanger.ac.uk"
	base_url = 'https://grit-jira.sanger.ac.uk/'
	rest_extension = 'rest/api/2/'

	def __init__(self, name):
		self.name = name
		self.debug_mode = False
		self._issue_json = None

	def rest_get(self, url):

		if self.debug_mode == True:
			print(url)

		my_netrc = netrc.netrc()
		response = requests.get(url, auth=(my_netrc.authenticators(self.host_name)[0], my_netrc.authenticators(self.host_name)[2]))
		return response.json()

	def rest_put(self, url, data_to_put):

		if self.debug_mode == True:
			print(url)

		my_netrc = netrc.netrc()
		response = requests.put(url, headers={'content-type': 'application/json'}, auth=(my_netrc.authenticators(self.host_name)[0], my_netrc.authenticators(self.host_name)[2]), data = json.dumps(data_to_put))

		if response.status_code != 204:
			exit('Failed to update JIRA')

		return

	@property
	def project_json(self):
		if self._issue_json == None:
			jira_method = 'search/'
			parameters = "jql=project%20%3D%20" + self.name + "%20ORDER%20BY%20created%20DESC&fields=key&maxResults=10000"

			url = self.base_url + self.rest_extension + jira_method + '?' + parameters
			self._project_json = self.rest_get(url)
		return self._project_json
	
	def get_issue_keys(self):
		issue_keys = []
		for issue in self.project_json['issues']:
			issue_keys.append(issue['key'])
#		print(self.project_json)
		return(issue_keys)