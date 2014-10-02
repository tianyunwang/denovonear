""" Script to generate mutation rates based on local sequence context rates
for Ensembl transcript IDs.
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import sys
import os
import copy
import math
import argparse

from src.load_gene import construct_gene_object
from src.ensembl_requester import EnsemblRequest
from src.load_mutation_rates import load_trincleotide_mutation_rates
from src.site_specific_rates import SiteRates

def get_options():
    """ get the command line switches
    """
    
    parser = argparse.ArgumentParser(description="determine mutation rates \
        for genes given transcript IDs.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--transcripts", dest="transcript_input",
        help="Path to file listing Ensembl transcript IDs.")
    group.add_argument("--genes", dest="gene_input", help="Path to file" + \
        " listing HGNC symbols, with one or more transcript IDs per gene.")
    
    parser.add_argument("--out", dest="output", required=True, help="output \
        filename")
    parser.add_argument("--rates", dest="mut_rates", required=True, \
        help="Path to file containing trinucleotide mutation rates.")
    parser.add_argument("--genome-build", dest="genome_build", choices=["grch37",
        "GRCh37", "grch38", "GRCh38"], default="grch37", help="Genome build "+ \
        "that the de novo coordinates are based on (GrCh37 or GRCh38")
    parser.add_argument("--cache-folder", dest="cache_folder", \
        default=os.path.join(os.path.dirname(__file__), "cache"), help="folder \
        to cache Ensembl data into (defaults to clustering code directory)")
    
    args = parser.parse_args()
    
    return args.transcript_input, args.gene_input, args.output, args.mut_rates, \
        args.cache_folder, args.genome_build.lower()

def load_transcripts(path):
    """ load a file listing transcript IDs per line
    
    Args:
        path: path to file containing transcript IDs, one per line
    
    Returns:
        list of transcript IDs eg ["ENST00000315684", "ENST00000485511"]
    """
    
    transcripts = {}
    with open(path, "r") as f:
        for line in f:
            transcripts[line.strip()] = line.strip()
            
    return transcripts
    
def load_genes(path):
    """ load a file listing gene and transcript IDs
    
    Eeach gene can have one or more transcript IDs associated with it, so we
    build a dictionary, indexed by HGNC symbols, and for each gene entry, retain
     a list of the possible transcript IDs.
    
    Args:
        path: path to file containing gene and transcript IDs, with each unique
            transcript ID for a gene on different lines eg
            
            gene_1    transcript_1.1    length_1    denovo_count
            gene_1    transcript_1.2    length_2    denovo_count
            gene_1    transcript_1.2    length_3    denovo_count
            gene_2    transcript_2.1    length_3    denovo_count
    
    Returns:
        list of transcript IDs eg ["ENST00000315684", "ENST00000485511"]
    """
    
    transcripts = {}
    with open(path, "r") as f:
        for line in f:
            if line.startswith("hgnc"):
                continue
            
            line = line.strip().split("\t")
            gene_id = line[0]
            transcript_id = line[1]
            
            if gene_id not in transcripts:
                transcripts[gene_id] = []
            
            transcripts[gene_id].append(transcript_id)
            
    return transcripts

def get_mutation_rate(gene_id, transcripts, mut_dict, ensembl):
    """ determines the missense and nonsense mutation rates for a gene
    
    This can estimate a mutation rate from the union of transcripts for a gene.
    This is a biased estimate of the mutation rate, where the mutation rate
    estimates is biased towards the rate from the first-ranked transcripts,
    which I prioritise by how many de novos they contain, and how long the
    coding sequence is.
    
    This isn't a problem when different transcripts have the same coding
    sequence within their shared regions, as the rates will come outthe same,
    but may differ two transcript share an overlapping region, but not in the
    same frame, so that the sites that are missense, and nonsense will differ
    between transcripts, and thus would produce different estimates of the
    mutation rate.
    
    Args:
        gene_id: ID for the current gene (can be a transcript ID, if we are
            examining single transcripts only, or can be a HGNC ID, if we are
            examining the union of mutation rates from multiple transcripts for
            a single gene).
        transcripts: dictionary of transcripts for a gene, indexed by gene_id
        mut_dict: dictionary of local sequence context mutation rates
        ensembl: EnsemblRequest object, to retrieve information from Ensembl.
    
    Returns:
        tuple of (missense, nonsense) mutation rates
    """
    
    missense = 0
    nonsense = 0
    combined_transcript = None
    
    for transcript_id in transcripts[gene_id]:
        
        transcript = construct_gene_object(ensembl, transcript_id)
        if combined_transcript is None:
            site_weights = SiteRates(transcript, mut_dict)
            combined_transcript = copy.deepcopy(transcript)
        else:
            site_weights = SiteRates(transcript, mut_dict, masked_sites=combined_transcript)
            combined_transcript += transcript
        
        missense_rates = site_weights.get_missense_rates_for_gene()
        nonsense_rates = site_weights.get_nonsense_rates_for_gene()
        
        # if any sites have been sampled in the transcript, then add the
        # cumulative probability from those sites to the approporiate
        # mutation rate. Sometimes we won't have any sites for a trsncript, as
        # all the sites will have been captured in previous transcripts.
        if len(missense_rates.choices) > 0:
            missense += missense_rates.cum_probs[-1]
        if len(nonsense_rates.choices) > 0:
            nonsense += nonsense_rates.cum_probs[-1]
    
    return (missense, nonsense)

def main():
    
    input_transcripts, input_genes, output_file, rates_file, cache_dir, genome_build = get_options()
    
    # load all the data
    ensembl = EnsemblRequest(cache_dir, genome_build)
    mut_dict = load_trincleotide_mutation_rates(rates_file)
    
    if input_transcripts is not None:
        transcripts = load_transcripts(input_transcripts)
    else:
        transcripts = load_genes(input_genes)
    
    output = open(output_file, "w")
    output.write("transcript_id\tmissense_rate\tnonsense_rate\n")
    
    for gene_id in transcripts:
        (missense, nonsense) = get_mutation_rate(gene_id, transcripts, mut_dict, ensembl)
        
        # log transform the rates, to keep them consistent with the rates from
        # Daly et al.
        missense = math.log10(missense)
        nonsense = math.log10(nonsense)
        
        line = "{0}\t{1}\t{2}\n".format(gene_id, missense, nonsense)
        output.write(line)
        
    output.close()

if __name__ == '__main__':
    main()





