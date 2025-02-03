#!/usr/bin/env python3

import sys

def fasta_length(path_to_fasta_file):
    """Calculate lengths of sequences in FASTA file."""
    length = 0
    with open(path_to_fasta_file) as f:
        for line in f:
            if line.startswith('>'):
                if length > 0:
                    print(f"{length} {header}")
                header = line[1:].strip()
                length = 0
            else:
                length += len(line.strip())
        if length > 0:
            print(f"{length} {header}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: sequence_length.py <fasta_file>")
    fasta_length(sys.argv[1])