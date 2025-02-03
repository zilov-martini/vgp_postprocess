import requests
import netrc
import json
import subprocess
import re
import GritJiraAuth
import GritJiraIssue

class GritJiraQuery:
	host_name = "jira.sanger.ac.uk"
	base_url = 'https://jira.sanger.ac.uk/'
	rest_extension = 'rest/api/2/'

	def __init__(self):
		self.debug_mode = False

	def rest_get(self, url):

		if self.debug_mode == True:
			print(url)

		my_netrc = netrc.netrc()
		response = requests.get(url, auth=GritJiraAuth.GritJiraAuth(my_netrc.authenticators(self.host_name)[0],my_netrc.authenticators(self.host_name)[2]))
		return response.json()

	def jql_query_to_json_result(self, jql_query, start_at = 0):
		url = self.base_url + self.rest_extension + f'search?jql={jql_query}' + f'&maxResults=1000&startAt={start_at}'
		return self.rest_get(url)

	def get_issue_keys_for_query(self, jql_query):

		issue_keys = []
	
		start_at = 0
		while True:
			max_results = 1000
			result_json = self.jql_query_to_json_result(jql_query, start_at=start_at)
			issue_keys_for_current_query = []
			if 'issues' in result_json:
				for issue in result_json['issues']:
					issue_keys_for_current_query.append(issue['key'])
				issue_keys += issue_keys_for_current_query
				if len(issue_keys_for_current_query) < max_results:
					break
				start_at += max_results

		return(issue_keys)

	def get_issue_keys_for_tolid(self, tolid):
		jql_query = f'(project = "ToL Rapid Curation" or project="ToL Assembly curation" or project="ToL Draft Submission") and status != Cancelled and "Sample ID" ~ "{tolid}"'

		# Check that the TOLID is an exact match
		valid_keys = []
		for key in self.get_issue_keys_for_query(jql_query):
			jira_issue = GritJiraIssue.GritJiraIssue(key)
			if jira_issue.get_custom_field('sample_id') == tolid:
				valid_keys.append(key)
		return valid_keys

	def get_issue_keys_for_species(self, species):
		jql_query = f'(project = "ToL Rapid Curation" or project="ToL Assembly curation" or project="ToL Draft Submission") and status != Cancelled and "Species Name" ~ "{species}"'
		return self.get_issue_keys_for_query(jql_query)
