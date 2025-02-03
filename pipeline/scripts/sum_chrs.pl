#!/usr/bin/env perl

use strict;
use Bio::SeqIO;
use Getopt::Long;

my $chrfile;
my $fastafile;

GetOptions (
    "chr:s" => \$chrfile,
    "fa:s"  => \$fastafile,
);

die "Usage: perl sum_chrs.pl -chr <chr_file> -fa <fa_file>\n" unless ($chrfile && $fastafile);

my %chr;
my %unlocalised;
my %sex_chr;
open(CHR,$chrfile);
while (<CHR>) {
#    if  (/^(\S+),\S+,/) {
#        $chr{$1}++;
#    }
#    elsif (/^(\S+)\s/) {
#        $chr{$1}++;
#    }
#    else {
#        die("nothing to see in the chr file!\n");
#    }

    my $split_char;
    if (/^(\S+),\S+,/) {
        $split_char = ',';
    }
    elsif (/^(\S+)\s/) {
        $split_char = '\s+';
    }
    else {
        die("I'm confused with $_\n");
    }

    my @fields = split(/$split_char/, $_);

    if(exists($fields[2]) and $fields[2] =~ /^no/i) {
        $unlocalised{$fields[0]}++;
    }
    else {
        $chr{$fields[0]}++;
    }
    if ($fields[1] =~ /^[XYZW]/i) {
        $sex_chr{$fields[1]}++;
    }

}

my $seqio = Bio::SeqIO->new('-format' => 'fasta',
                            '-file'   => $fastafile);
  
my $totallength;
my $chrlength;
my $count;
my $unlocalised_count = 0;
my $mt_flag = 0;
     
my %seen;                            
while (my $seqobj = $seqio->next_seq()) {
    my $len    = $seqobj->length(); 
    my $id     = $seqobj->display_id();
    $seen{$id}++;

    if($id eq 'scaffold_MT') {
        $mt_flag = 1;
    }
    else {
        $totallength += $len;
        $chrlength += $len if (exists $chr{$id} or exists $unlocalised{$id});    
        $count++ if (exists $chr{$id});
        $unlocalised_count++ if (exists $unlocalised{$id});
    }
}

# safety check
my @all_scaffolds = keys %chr;
push(@all_scaffolds, keys %unlocalised);
foreach my $scaff (@all_scaffolds) {
    print "Error: $scaff not in fasta file!\n" unless (exists $seen{$scaff});
    
}

my $some_word;
my @sex_chr_list = sort {$a cmp $b} keys %sex_chr;
my $sex_chr_string;
if(scalar @sex_chr_list == 0) {
    $sex_chr_string = '';
    $some_word = 'chromosomes';
}
else {
    $some_word = 'autosomes';
    $sex_chr_string = ' and ';
    if(scalar @sex_chr_list == 1) {
        $sex_chr_string .= $sex_chr_list[0];
    }
    elsif(scalar @sex_chr_list == 2) {
        $sex_chr_string .= "$sex_chr_list[0] and $sex_chr_list[1]";
    }
    else {
        $sex_chr_string .= join(',', @sex_chr_list[0 .. $#sex_chr_list-1]);
        $sex_chr_string .= " and $sex_chr_list[-1]";
    }
    $count -= scalar(@sex_chr_list);
}
my $unlocalised_string = '';
if ($unlocalised_count > 0) {
    $unlocalised_string = " (plus $unlocalised_count unlocalised)";
}

my $mt_string = '';
if ($mt_flag) {
    $mt_string = ' and MT'
}

print "found $count $some_word$sex_chr_string$mt_string$unlocalised_string\n";
print "Total length $totallength\n";
print "Chr length $chrlength\n";
print "Chr length ", int($chrlength*10000/$totallength)/100," %\n";

