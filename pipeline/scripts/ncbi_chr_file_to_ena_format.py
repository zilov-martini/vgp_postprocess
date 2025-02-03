#!/usr/bin/env python

import re
import csv
import sys
import os
import argparse

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("ncbi_chromosome_list_file")
	parser.add_argument("--chr_out")
	parser.add_argument("--unlocalised_out")
	args = parser.parse_args()

	# Create output files
	ena_chromosome_list_file = args.ncbi_chromosome_list_file + '.ena.localised'
	if args.chr_out != None:
		ena_chromosome_list_file = args.chr_out
	ena_unlocalised_list_file = args.ncbi_chromosome_list_file + '.ena.unlocalised'
	if args.unlocalised_out != None:
		ena_unlocalised_list_file = args.unlocalised_out

	ena_chromosome_list_handle = open(ena_chromosome_list_file, 'w', newline='')
	ena_chromosome_list_writer = csv.writer(ena_chromosome_list_handle, delimiter='\t')

	ena_unlocalised_list_handle = open(ena_unlocalised_list_file, 'w', newline='')
	ena_unlocalised_list_writer = csv.writer(ena_unlocalised_list_handle, delimiter='\t')

	with open(args.ncbi_chromosome_list_file, 'r') as ncbi_chromosome_list_handle:
		for row in ncbi_chromosome_list_handle:
			fields = re.split( ',', row.rstrip() )
			if len(fields) != 3:
				print('Non-standard line format: ' + row + ': field-count ' + str(len(fields)))
			if fields[2] == 'yes':
				fields[2] = 'Chromosome'
				ena_chromosome_list_writer.writerow(fields)
			elif fields[2] == 'no':
				fields.pop()
				ena_unlocalised_list_writer.writerow(fields)
			else:
				exit('Non-standard line format: ' + row)				

	ena_chromosome_list_handle.close()
	ena_unlocalised_list_handle.close()

if __name__ == "__main__":
		main()
